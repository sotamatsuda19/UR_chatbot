import re
import json
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────────────
# Helper: fix instructor name
# ─────────────────────────────────────────────────────────────────────────────

def fix_instructor(name):
    """
    Removes leading '; ' artifacts caused by page-break cutoffs.

    '; John Lin'        →  'John Lin'
    'Hari Rau-Murthy'   →  'Hari Rau-Murthy'   (unchanged)
    'Smith; Jane Doe'   →  'Smith; Jane Doe'    (unchanged — valid multi-instructor)
    ''                  →  ''                   (unchanged)
    """
    return re.sub(r'^[;\s]+', '', name)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: strip section number from course code
# ─────────────────────────────────────────────────────────────────────────────

def base_code(full_code):
    """
    Extracts the base course code by removing the section number.

    'MATH 162-03'  →  'MATH 162'
    'CHB 411-01'   →  'CHB 411'
    'ACC 221'      →  'ACC 221'   (no section number, unchanged)
    """
    return re.sub(r'-\d{1,3}$', '', full_code).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: pick the best value for a shared text field
# ─────────────────────────────────────────────────────────────────────────────

def best_field(sections, field):
    """
    Among all sections, returns the longest non-empty value for a given field.
    Prefers Lecture sections first, then falls back to any section.
    Longer = more complete (handles cases where a section had a page-break cutoff).
    """
    best = ""
    # First pass: lecture sections only
    for s in sections:
        value = s.get(field, "").strip()
        if s["type"] == "Lecture" and len(value) > len(best):
            best = value

    # Second pass: any section (if no lecture had content)
    if not best:
        for s in sections:
            value = s.get(field, "").strip()
            if len(value) > len(best):
                best = value

    return best


# ─────────────────────────────────────────────────────────────────────────────
# Main: merge sections of the same course
# ─────────────────────────────────────────────────────────────────────────────

def merge_courses(courses):
    """
    Groups all sections of the same course (e.g. MATH 162-01 through 162-08)
    into a single entry.

    Shared fields (title, description, notes, restrictions, offered, credits)
    are taken from the best available section.

    Each section becomes an item in the 'sections' list, keeping its own
    schedule, instructor, enrolled, capacity, status, and type.

    A 'section_counts' dict shows how many Lectures, Recitations, Labs, etc.
    """
    # Group sections by base code
    groups = defaultdict(list)
    for course in courses:
        key = base_code(course["code"])
        groups[key].append(course)

    merged = []

    for key, sections in groups.items():
        # Sort: Lectures first, then by section id for consistency
        sections.sort(key=lambda s: (s["type"] != "Lecture", s["code"]))

        # Count how many of each type exist
        section_counts = defaultdict(int)
        for s in sections:
            section_counts[s["type"]] += 1

        merged_course = {
            "code":         key,
            "title":        sections[0]["title"],
            "credits":      sections[0]["credits"],
            "offered":      best_field(sections, "offered"),
            "description":  best_field(sections, "description"),
            "notes":        best_field(sections, "notes"),
            "restrictions": best_field(sections, "restrictions"),

            # e.g. {"Lecture": 3, "Recitation": 5}
            "section_counts": dict(section_counts),

            # Each original section kept as a compact record
            "sections": [
                {
                    "section_id": s["code"],         # "MATH 162-03"
                    "type":       s["type"],          # "Lecture" / "Recitation" / ...
                    "term":       s["term"],
                    "status":     s["status"],        # "Open" / "Closed"
                    "schedule":   s["schedule"],      # list of {days, start_time, end_time}
                    "enrolled":   s["enrolled"],
                    "capacity":   s["capacity"],
                    "instructor": fix_instructor(s["instructor"]),
                }
                for s in sections
            ],
        }

        merged.append(merged_course)

    # Sort final list alphabetically by course code
    merged.sort(key=lambda c: c["code"])
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def clean_json(input_path, output_path):
    with open(input_path, "r") as f:
        courses = json.load(f)
    print(f"Loaded {len(courses)} sections")

    merged = merge_courses(courses)

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"Merged into {len(merged)} unique courses → {output_path}")


if __name__ == "__main__":
    clean_json("courses.json", "courses_clean.json")
