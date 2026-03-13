import re
import json


# ─────────────────────────────────────────────────────────────────────────────
# Patterns
# ─────────────────────────────────────────────────────────────────────────────

# Matches timestamp lines like "3/1/26, 12:29 AM ..."
TIMESTAMP_PAT = re.compile(r'^\d{1,2}/\d{1,2}/\d{2,4},')

# Matches a course header line, e.g.:
#   "ACC 221-01 Managerial Accounting Lecture Spring 2026 4.0 Open"
#   "AHST 1000-01 Teaching Assistantship Internship Spring 2026 Internship Open"
COURSE_HEADER_PAT = re.compile(
    r'^([A-Z]{2,5}\s+\d{3,4}(?:-\d{1,3})?)'    # code:    "ACC 221-01"
    r'\s+(.+?)'                              # title:   lazy match stops before type
    r'\s+(Lecture|Seminar|Lab|Recitation'
    r'|Independent Study|Internship'
    r'|Research|Studio|Conference|Discussion)'
    r'\s+(Fall|Spring|Summer|Winter)'        # season
    r'\s+\d{4}'                              # year — captured but not stored
    r'\s+([\d.]+(?:\s*-\s*[\d.]+)?'         # credits: "4.0" or "0.0 - 4.0"
    r'|Internship|Research'                  #          or a word when PDF repeats the type
    r'|Lecture|Seminar|Lab|Recitation'       #          e.g. "CHB 411-01 ... Lecture Open"
    r'|Independent Study|Studio'
    r'|Conference|Discussion)'
    r'\s+(Open|Closed|Waitlist|Cancelled)'
)

# Matches a schedule line, e.g.:
#   "MW 1230 PM 145 PM"   "TR 940 AM 1055 AM"   "F 100 PM 150 PM"
# Note: R = Thursday (avoids conflict with T = Tuesday)
SCHEDULE_PAT = re.compile(
    r'^([MTWRFS]+)'             # days
    r'\s+(\d{3,4}\s+[AP]M)'    # start time: "1230 PM"
    r'\s+(\d{3,4}\s+[AP]M)'    # end time:   "145 PM"
)

# Matches exactly two numbers: "83 86"  →  enrolled, capacity  (Format A)
TWO_NUMS_PAT = re.compile(r'^(\d+)\s+(\d+)$')

# Matches exactly one number: "4" or "90"  (Format B, single per line)
ONE_NUM_PAT = re.compile(r'^(\d+)$')

# Maps section-opening keywords to the dict field they fill
SECTION_KEYWORDS = {
    "Description:":  "description",
    "Public Notes:": "notes",
    "Restrictions:": "restrictions",
    "Instructors:":  "instructor",   # always one line
    "Offered:":      "offered",      # always one line
}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — clean_txt
# Remove every line that is pure noise.
# Returns a list of stripped, non-empty strings.
# ─────────────────────────────────────────────────────────────────────────────

NOISE_PREFIXES = [
    "https",                    # URL footers
    "Course Course Title",      # table column header
    "Schedule: Day Begin",      # table column header
    "Books: Click",             # bookstore button text
    "Delivery",                 # "Delivery In-Person" or "Delivery\nMode:"
    "Mode:",                    # leftover from split "Delivery Mode:"
    "Co-Located:",              # cross-listed sections (not needed for chatbot)
    "UR Course Descriptions",   # page header title
]

def clean_txt(txt_path):
    clean_lines = []
    with open(txt_path, "r") as f:
        for line in f:
            stripped = line.strip()

            if not stripped:
                continue
            if TIMESTAMP_PAT.match(stripped):
                # NOTE: if the timestamp is prepended to useful content
                # e.g. "3/1/26, 12:29 AM Enrollment: Enrolled", that line
                # is lost. This is a rare edge case — acceptable for now.
                continue
            if any(stripped.startswith(p) for p in NOISE_PREFIXES):
                continue

            clean_lines.append(stripped)

    return clean_lines


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — parse_courses
# Walks through clean lines with a state machine.
# Returns a list of course dicts.
#
# Two state variables run in parallel:
#   section      — which text field we are currently appending lines to
#                  ("description", "notes", "restrictions", or None)
#   enroll_state — where we are in reading enrollment numbers
#                  (None, "need_two", "need_enrolled", "need_capacity")
# ─────────────────────────────────────────────────────────────────────────────

def parse_courses(lines):
    courses      = []
    current      = None   # dict for the course being built
    section      = None
    enroll_state = None

    for line in lines:

        # ── new course header ─────────────────────────────────────────────────
        m = COURSE_HEADER_PAT.match(line)
        if m:
            if current:
                courses.append(current)   # save the finished course
            current = {
                "code":         m.group(1).strip(),   # "ACC 221-01"
                "title":        m.group(2).strip(),   # "Managerial Accounting"
                "type":         m.group(3),           # "Lecture"
                "term":         m.group(4),           # "Spring"
                "credits":      m.group(5),           # "4.0"
                "status":       m.group(6),           # "Open"
                "schedule":     [],                   # list of {days, start, end}
                "enrolled":     None,
                "capacity":     None,
                "instructor":   "",
                "description":  "",
                "notes":        "",
                "restrictions": "",
                "offered":      "",
            }
            section      = None
            enroll_state = None
            continue

        # ignore lines before the very first course in the file
        if current is None:
            continue

        # ── schedule line ─────────────────────────────────────────────────────
        m = SCHEDULE_PAT.match(line)
        if m:
            current["schedule"].append({
                "days":       m.group(1),   # "MW"
                "start_time": m.group(2),   # "1230 PM"
                "end_time":   m.group(3),   # "145 PM"
            })
            section = None
            continue

        # ── enrollment lines ──────────────────────────────────────────────────
        # Format A: "Enrollment: Enrolled Capacity"  → next line is "83 86"
        # Format B: "Enrollment: Enrolled"           → next lines are "4", "Capacity", "25"
        if line.startswith("Enrollment:"):
            enroll_state = "need_two" if "Capacity" in line else "need_enrolled"
            section = None
            continue

        if line == "Capacity":
            # standalone "Capacity" column label in Format B — just skip it
            # (enroll_state stays as "need_capacity", set by the number handler below)
            continue

        m = TWO_NUMS_PAT.match(line)
        if m and enroll_state == "need_two":
            current["enrolled"] = int(m.group(1))
            current["capacity"] = int(m.group(2))
            enroll_state = None
            continue

        m = ONE_NUM_PAT.match(line)
        if m:
            n = int(m.group(1))
            if enroll_state == "need_enrolled":
                current["enrolled"] = n
                enroll_state = "need_capacity"
                continue
            elif enroll_state == "need_capacity":
                current["capacity"] = n
                enroll_state = None
                continue

        # ── section keyword lines ─────────────────────────────────────────────
        matched = False
        for keyword, field in SECTION_KEYWORDS.items():
            if line.startswith(keyword):
                rest = line[len(keyword):].strip()   # text after the keyword
                if field in ("instructor", "offered"):
                    # single-line fields — store immediately, reset section
                    current[field] = rest
                    section = None
                else:
                    # multi-line fields — store first line, keep section open
                    current[field] = rest
                    section = field
                matched = True
                break
        if matched:
            continue

        # ── continuation of a multi-line section ─────────────────────────────
        if section in ("description", "notes", "restrictions"):
            current[section] += " " + line

    # save the very last course in the file
    if current:
        courses.append(current)

    return courses


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — save_json
# ─────────────────────────────────────────────────────────────────────────────

def save_json(courses, output_path):
    with open(output_path, "w") as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(courses)} courses → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# Run:  python txt2json.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lines   = clean_txt("output.txt")
    courses = parse_courses(lines)
    save_json(courses, "courses.json")
