import re
import requests
import json
import time
import os
from urllib.parse import urljoin, urlparse
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY from environment automatically


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

START_URL   = "https://www.rochester.edu/academics/programs.html"

# Absolute path — saves next to this script regardless of where you run it from
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "academic_info.json")
SLEEP_SECONDS = 1.5

MAX_DEPTH = 2

# How many sub-links GPT is allowed to select per page at each depth.
# Gets stricter as we go deeper to prevent exponential growth.
MAX_LINKS_PER_DEPTH = {1: 5, 2: 5, 3: 4, 4: 3, 5: 0}

# URL prefixes to skip when collecting links from the index page
INDEX_SKIP_PREFIXES = [
    "https://www.rochester.edu/admissions",
    "https://www.rochester.edu/visit",
    "https://www.rochester.edu/about",
    "https://www.rochester.edu/research",
    "https://www.rochester.edu/working",
    "https://www.rochester.edu/assets",
    "https://everbetter.rochester.edu",
    "https://www.rochester.edu/academics/programs",  # the index page itself
]

# URL patterns that indicate a page is NOT useful academic content.
# Any URL containing one of these strings is skipped entirely.
BLOCKED_PATTERNS = [
    "/news/", "/events/", "/calendar/",
    "/people/", "/faculty/", "/staff/", "/directory/",
    "/gallery/", "/photos/", "/media/",
    "/blog/", "/giving/", "/donate/",
    "/jobs/", "/careers/", "/employment/",
    "/login", "/secure", "/forms/",
    "mailto:", ".pdf", ".jpg", ".jpeg", ".png", ".gif",
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: Fetch any webpage as clean text using Jina Reader (free, no key)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_page(url):
    try:
        response = requests.get(f"https://r.jina.ai/{url}", timeout=30)
        if response.status_code == 200:
            return response.text
        print(f"  Failed ({response.status_code}): {url}")
        return None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: Extract all program URLs from the index page using regex
# (regex instead of GPT — reads the full 160+ program list without truncation)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_program_urls(index_text):
    all_urls = re.findall(r'\((https?://[^\s\)]+rochester\.edu[^\s\)]*)\)', index_text)
    seen = set()
    filtered = []
    for url in all_urls:
        if url in seen:
            continue
        seen.add(url)
        if any(url.startswith(p) for p in INDEX_SKIP_PREFIXES):
            continue
        filtered.append(url)
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: Check whether a URL should be skipped
# ─────────────────────────────────────────────────────────────────────────────

def resolve_url(base_url, sub_url):
    """
    Converts a relative URL to an absolute URL using the base page's URL.
    Also strips fragment anchors (#section) since they don't load a new page.

    Examples:
      base="https://www.sas.rochester.edu/cs/", sub="undergraduate/major.html"
      → "https://www.sas.rochester.edu/cs/undergraduate/major.html"

      base="https://www.sas.rochester.edu/cs/", sub="/college/curriculum/"
      → "https://www.sas.rochester.edu/college/curriculum/"

      base="https://www.sas.rochester.edu/cs/", sub="requirements.html#section3"
      → "https://www.sas.rochester.edu/cs/requirements.html"  (fragment stripped)
    """
    resolved = urljoin(base_url, sub_url)

    # Strip fragment — "#section" is just a scroll anchor, not a new page
    resolved = resolved.split("#")[0]

    # Must be a rochester.edu URL after resolving
    if "rochester.edu" not in urlparse(resolved).netloc:
        return None

    return resolved


def is_blocked(url):
    """
    Returns True if the URL should never be visited.
    Blocks non-rochester.edu domains and known useless page types.
    """
    if "rochester.edu" not in url.lower():
        return True
    if any(pattern in url.lower() for pattern in BLOCKED_PATTERNS):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4: GPT analyzes one page — behavior changes based on depth
#
#   depth == 1  →  extract department overview (broad picture)
#   depth > 1   →  extract specific requirements, opportunities, programs
#   depth == 5  →  extract only, never suggest sub-links
# ─────────────────────────────────────────────────────────────────────────────

def analyze_page(page_text, url, depth):
    """
    One GPT-4o-mini call per page.
    Returns a dict with:
        has_content   — false if the page is useless (login, error, navigation only)
        department    — detected department name
        school        — detected school name
        text          — extracted content as clean paragraphs
        sub_links     — up to MAX_LINKS_PER_DEPTH[depth] relevant URLs to follow next
    """

    max_links = MAX_LINKS_PER_DEPTH.get(depth, 0) if depth < MAX_DEPTH else 0

    # What to extract changes depending on depth
    if depth == 1:
        extract_instruction = (
            "Extract a thorough overview of this academic department including:\n"
            "- What the department studies and its academic identity\n"
            "- What makes it unique at the University of Rochester\n"
            "- Main research areas and academic strengths\n"
            "- General career paths and outcomes for graduates\n"
            "- Any notable programs, honors tracks, or special opportunities\n"
            "Write in clear, informative paragraphs. Do not use bullet points."
        )
    else:
        extract_instruction = (
            "Extract all of the following that appear on this page:\n"
            "- Major requirements (copy exact wording)\n"
            "- Minor requirements (copy exact wording)\n"
            "- Cluster requirements (copy exact wording)\n"
            "- Honors or accelerated degree programs\n"
            "- Undergraduate research opportunities\n"
            "- Study abroad options and how they affect requirements\n"
            "- Combined or dual degree programs\n"
            "- Any academic policies specific to this department\n"
            "Preserve original wording. Do not paraphrase."
        )

    if max_links > 0:
        link_instruction = (
            f"Also select up to {max_links} sub-links from this page that would "
            f"lead to more detailed academic content (requirements, programs, opportunities).\n"
            f"Only include links from *.rochester.edu. "
            f"Never include links to news, events, people, staff, photos, or giving pages."
        )
    else:
        link_instruction = "Do not suggest any sub-links. sub_links must be []."

    # Wrap the entire API call + parse in one try/except.
    # Without this, any network error or rate limit from OpenAI crashes the script.
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze University of Rochester academic webpages for a student information chatbot.\n\n"
                        "Return a JSON object with this exact structure:\n"
                        "{\n"
                        '  "has_content": true or false,\n'
                        '  "department": "full department name, or empty string",\n'
                        '  "school": "school name e.g. School of Arts and Sciences, or empty string",\n'
                        '  "text": "extracted content as described in the instructions",\n'
                        '  "sub_links": ["url1", "url2"]\n'
                        "}\n\n"
                        "has_content must be a boolean true or false, never a string.\n"
                        "sub_links must always be a list, never null.\n"
                        "has_content = false only if the page contains no useful academic information "
                        "(e.g. a login page, 404 error, or pure navigation page with no content)."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Analyze this depth-{depth} University of Rochester page.\n\n"
                        f"URL: {url}\n\n"
                        f"{extract_instruction}\n\n"
                        f"{link_instruction}\n\n"
                        f"Page content:\n{page_text[:50000]}"
                    )
                }
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"  GPT error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main agent loop
# ─────────────────────────────────────────────────────────────────────────────

def run_agent():
    all_documents = []
    visited = set()

    # ── Step 1: fetch the index page ─────────────────────────────────────────
    print("Step 1: Fetching program index page...")
    index_text = fetch_page(START_URL)
    if not index_text:
        print("Could not fetch index page. Check START_URL.")
        return
    visited.add(START_URL)

    # ── Step 2: extract all program URLs from the index ───────────────────────
    print("\nStep 2: Extracting program URLs...")
    program_urls = get_all_program_urls(index_text)
    print(f"  Found {len(program_urls)} unique program URLs")

    # ── Step 3: build the initial queue ──────────────────────────────────────
    # Each queue item is a dict so we can track depth, department, and school.
    queue = []

    for url in program_urls:
        queue.append({"url": url, "depth": 1, "department": "", "school": ""})

    # ── Step 4: process the queue ─────────────────────────────────────────────
    print(f"\nStep 3: Crawling pages (max depth {MAX_DEPTH})...\n")

    i = 0
    while i < len(queue):
        item  = queue[i]
        i    += 1
        url   = item["url"]
        depth = item["depth"]

        if url in visited or is_blocked(url):
            continue
        visited.add(url)

        print(f"[{i}/{len(queue)}] depth={depth}  {url}")

        page_text = fetch_page(url)
        if not page_text:
            time.sleep(SLEEP_SECONDS)
            continue

        result = analyze_page(page_text, url, depth)
        if not result:
            time.sleep(SLEEP_SECONDS)
            continue

        # Skip pages with no useful content.
        # has_content could be False (boolean) or "false" (string from GPT).
        # str(x).lower() handles both safely.
        has_content = result.get("has_content", True)
        if str(has_content).lower() == "false":
            print("  skip — no useful content")
            time.sleep(SLEEP_SECONDS)
            continue

        # Prefer GPT's detected department/school over the parent's
        department = result.get("department") or item["department"]
        school     = result.get("school")     or item["school"]
        content_type = "department_overview" if depth == 1 else "requirements"

        document = {
            "url":          url,
            "department":   department,
            "school":       school,
            "depth":        depth,
            "content_type": content_type,
            "text":         text if isinstance((text := result.get("text", "")), str) else "",
        }

        all_documents.append(document)
        print(f"  ✓ [{content_type}] {department}")

        # Save after every page — crash-safe
        with open(OUTPUT_FILE, "w") as f:
            json.dump(all_documents, f, indent=2, ensure_ascii=False)

        # Add sub-links to queue if we haven't hit max depth
        if depth < MAX_DEPTH:
            max_links  = MAX_LINKS_PER_DEPTH.get(depth, 0)
            sub_links  = (result.get("sub_links") or [])[:max_links]
            new_count  = 0

            for raw_url in sub_links:
                if not isinstance(raw_url, str):
                    continue
                sub_url = resolve_url(url, raw_url)   # fix relative → absolute
                if not sub_url:
                    continue
                if sub_url not in visited and not is_blocked(sub_url):
                    queue.append({
                        "url":        sub_url,
                        "depth":      depth + 1,
                        "department": department,
                        "school":     school,
                    })
                    new_count += 1

            if new_count:
                print(f"  → queued {new_count} sub-links at depth {depth + 1}")

        time.sleep(SLEEP_SECONDS)

    print(f"\nDone.")
    print(f"  Pages visited : {len(visited)}")
    print(f"  Documents saved: {len(all_documents)}")
    print(f"  Output file   : {OUTPUT_FILE}")


if __name__ == "__main__":
    run_agent()
