import requests
import json
import re
import time
import os
from urllib.parse import urljoin, urlparse
from openai import OpenAI
from bs4 import BeautifulSoup

client = OpenAI()


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE   = os.path.join(SCRIPT_DIR, "gap_fill_data.json")
UNIFIED_FILE  = os.path.join(SCRIPT_DIR, "unified_ur_data.json")
CAMPUS_FILE   = os.path.join(SCRIPT_DIR, "campus_life_data.json")
SLEEP_SECONDS = 3.0

CHUNK_SIZE    = 1500
CHUNK_OVERLAP = 300
MIN_CHARS     = 100

BLOCKED_PATTERNS = [
    "/news/", "/events/",
    "/people/", "/faculty/", "/staff/", "/directory/",
    "/gallery/", "/photos/", "/media/", "/giving/", "/donate/", "/blog/",
    "/login", "/secure",
    "mailto:", ".jpg", ".jpeg", ".png", ".gif",
]

SEED_URLS = [
    "https://ccc.rochester.edu/club_signup?view=all&"
]

# depth-0 = seed pages, depth-1 = their sub-links, depth-2 = no further links
SEED_LINKS_PER_DEPTH = {0: 100, 1: 0, 2: 0}


# ─────────────────────────────────────────────────────────────────────────────
# Text cleaning  (mirrors process_campus_life.py)
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r"(?:Spring|Fall|Winter|Summer) Standard Hours of Operation.*?\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"All dining locations are currently (?:open|closed)\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"What'?s Open Now.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{1,2}:\d{2}\s?(?:am|pm|AM|PM)", "", text)
    text = re.sub(r"The information contained on this dining website.*?dining manager on duty\.", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(?:Location|Address):?\s?University of Rochester.*?\d{5}-\d{4}", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"Phone:?\s?\(?\d{3}\)?\s?\d{3}-\d{4}", "", text)
    text = re.sub(r"Email:?\s?\S+@\S+", "", text)
    text = re.sub(r"Lorem ipsum.*?(\.|\n)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:Upcoming Events|Upcoming Opportunities).*?(?=\n\n|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\b\d{10}\b", "", text)
    text = re.sub(r"\b(?:noon|midnight)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Skip to (?:Content|Navigation)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Accessibility Preferences", "", text, flags=re.IGNORECASE)
    text = re.sub(r"High Contrast", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Font Size.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Helpful [Ll]inks?:?.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"Resources for\n(?:\*[^\n]*\n)+", "", text)
    text = re.sub(r"\[([^\]]+)\]\((?!mailto)[^)]+\)", r"\1", text)
    text = re.sub(r"\[.*?\]\(mailto:[^\)]*\)", "", text)
    text = re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", text)
    text = re.sub(r"^[A-Z][^.\n]{10,100}\?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[\*\-]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^.*?\|\s*.*?\|\s*University of Rochester.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = re.sub(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "", text)
    text = re.sub(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\s*\|\s*\d{1,2}:\d{2}\s*(?:am|pm)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[-=]{3,}", "", text)
    text = re.sub(r"(\|\s*)+\|", "", text)
    text = re.sub(r"(?:[A-Z]\[?[A-Z]?\]?\s*){5,}", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"^[\*\-]\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,:;])", r"\1", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Chunking  (mirrors process_campus_life.py)
# ─────────────────────────────────────────────────────────────────────────────

def snap_to_boundary(text: str, pos: int) -> int:
    match = re.search(r"\s", text[pos:])
    if match:
        return pos + match.start() + 1
    return pos


def split_into_chunks(text: str) -> list[str]:
    chunks = []
    start  = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            window   = text[max(start, end - 200): end]
            boundary = window.rfind("\n")
            if boundary == -1:
                boundary = window.rfind(". ")
            if boundary != -1:
                end = max(start, end - 200) + boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        overlap_start = end - CHUNK_OVERLAP
        start = snap_to_boundary(text, max(overlap_start, 0))
        if start >= end:
            start = end
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Document builder — clean, chunk, append
# ─────────────────────────────────────────────────────────────────────────────

def append_document(all_documents, url, category, depth, raw_text):
    """Clean, chunk, and append one scraped page to all_documents."""
    text = clean_text(raw_text)
    if len(text) < MIN_CHARS:
        return 0

    meta = {
        "url":          url,
        "department":   category,
        "school":       "",
        "depth":        depth,
        "content_type": "campus_life",
    }

    if len(text) >= CHUNK_SIZE:
        chunks = split_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            entry = dict(meta)
            entry["text"]        = chunk
            entry["chunk_index"] = idx
            entry["chunk_total"] = len(chunks)
            all_documents.append(entry)
        return len(chunks)
    else:
        entry = dict(meta)
        entry["text"]        = text
        entry["chunk_index"] = 0
        entry["chunk_total"] = 1
        all_documents.append(entry)
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_url(url):
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(scheme="https", netloc=netloc, path=path,
                            fragment="").geturl()


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                a.replace_with(f"[{text}]({href})" if text else href)
            return soup.get_text(separator="\n", strip=True)
        print(f"  Failed ({response.status_code}): {url}")
        return None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def resolve_url(base_url, sub_url):
    resolved = urljoin(base_url, sub_url).split("#")[0]
    if "rochester.edu" not in urlparse(resolved).netloc:
        return None
    return normalize_url(resolved)


def is_blocked(url):
    if "rochester.edu" not in url.lower():
        return True
    return any(pattern in url.lower() for pattern in BLOCKED_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# GPT: extract sub-links
# ─────────────────────────────────────────────────────────────────────────────

def get_links_general(page_text, url, max_links=5):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze University of Rochester webpages.\n\n"
                        "Return a JSON object with this exact structure:\n"
                        '{"sub_links": ["url1", "url2"]}\n\n'
                        "sub_links must always be a list, never null."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Select up to {max_links} links from this page that a University of Rochester student and its applicants (prospective students) "
                        "would find most useful. Only include links from *.rochester.edu. "
                        "Exclude news, events, people directories, photos, and giving pages.\n\n"
                        f"URL: {url}\n\n"
                        f"Page content:\n{page_text[:50000]}"
                    )
                }
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("sub_links") or []
    except Exception as e:
        print(f"  GPT error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# GPT: extract page content
# ─────────────────────────────────────────────────────────────────────────────

def analyze_page_general(page_text, url):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze University of Rochester webpages for a student information chatbot.\n\n"
                        "Return a JSON object with this exact structure:\n"
                        "{\n"
                        '  "has_content": true or false,\n'
                        '  "category": "e.g. Housing, Dining, Transportation, Campus Life, Financial Aid, '
                        'Health & Wellness, Career Services, Athletics, IT Services, International Students, Registrar, Bursar",\n'
                        '  "text": "extracted content as a string"\n'
                        "}\n\n"
                        "has_content must be a boolean true or false, never a string.\n"
                        "has_content = false only if the page contains no useful student information "
                        "(e.g. a login page, 404 error, or pure navigation page with no content)."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"URL: {url}\n\n"
                        "Extract all information from this page that a University of Rochester student and its applicants (prospective students) "
                        "would find useful. Use your own judgment to decide what matters. "
                        "Preserve original wording — copy exact names, numbers, dates, and policy language rather than paraphrasing.\n\n"
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
# Main crawl
# ─────────────────────────────────────────────────────────────────────────────

def process_depth(queue, next_queue, depth, already_processed, visited, all_documents, max_links):
    """Fetch each URL in queue. Skip analyze/save if already processed, but always get sub-links."""
    for i, item in enumerate(queue):
        url = item["url"]
        already_done = url in already_processed

        if already_done:
            print(f"[{i+1}/{len(queue)}] depth={depth}  {url}  (links only)")
        else:
            print(f"[{i+1}/{len(queue)}] depth={depth}  {url}")

        if already_done and next_queue is None:
            continue

        page_text = fetch_page(url)
        if not page_text:
            time.sleep(SLEEP_SECONDS)
            continue

        if not already_done:
            result = analyze_page_general(page_text, url)
            if result and str(result.get("has_content", True)).lower() != "false":
                raw_text = result.get("text", "") if isinstance(result.get("text"), str) else ""
                n = append_document(all_documents, url, result.get("category", "Campus Life"), depth, raw_text)
                if n:
                    already_processed.add(url)
                    print(f"  ✓ [{result.get('category', 'Campus Life')}] → {n} chunk(s)")
                    with open(OUTPUT_FILE, "w") as f:
                        json.dump(all_documents, f, indent=2, ensure_ascii=False)
                else:
                    print("  skip — no useful content after cleaning")
            else:
                print("  skip — no useful content")

        if next_queue is not None and max_links > 0:
            sub_links = get_links_general(page_text, url, max_links=max_links)
            new_count = 0
            for raw_url in sub_links:
                if not isinstance(raw_url, str):
                    continue
                sub_url = resolve_url(url, raw_url)
                if not sub_url or sub_url in visited or is_blocked(sub_url):
                    continue
                next_queue.append({"url": sub_url, "seed": item["seed"]})
                visited.add(sub_url)
                new_count += 1
            if new_count:
                print(f"  → queued {new_count} depth-{depth+1} links")

        time.sleep(SLEEP_SECONDS)


def run_seed_crawl():
    # ── Load existing output documents (for resume) ───────────────────────────
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            all_documents = json.load(f)
        already_processed = {normalize_url(doc["url"]) for doc in all_documents}
        print(f"Loaded {len(all_documents)} existing chunks from {os.path.basename(OUTPUT_FILE)}")
    else:
        all_documents = []
        already_processed = set()

    # ── Also mark URLs from unified_ur_data.json and campus_life_data.json as visited ──
    for ref_file in (UNIFIED_FILE, CAMPUS_FILE):
        if os.path.exists(ref_file):
            with open(ref_file) as f:
                ref_docs = json.load(f)
            ref_urls = {normalize_url(doc["url"]) for doc in ref_docs}
            already_processed |= ref_urls
            print(f"Marked {len(ref_urls)} URLs from {os.path.basename(ref_file)} as already visited")

    visited = set(already_processed)
    print(f"Starting seed crawl from {len(SEED_URLS)} seed URLs\n")

    # ── Step 1: seed pages (depth 0) ─────────────────────────────────────────
    depth1_queue = []

    for i, seed_url in enumerate(SEED_URLS):
        seed_url = normalize_url(seed_url)

        if seed_url in visited and seed_url not in already_processed:
            print(f"[seed {i+1}/{len(SEED_URLS)}] skip (duplicate): {seed_url}")
            continue

        visited.add(seed_url)
        already_done = seed_url in already_processed

        if already_done:
            print(f"[seed {i+1}/{len(SEED_URLS)}] {seed_url}  (links only)")
        else:
            print(f"[seed {i+1}/{len(SEED_URLS)}] {seed_url}")

        page_text = fetch_page(seed_url)
        if not page_text:
            time.sleep(SLEEP_SECONDS)
            continue

        if not already_done:
            result = analyze_page_general(page_text, seed_url)
            if result and str(result.get("has_content", True)).lower() != "false":
                raw_text = result.get("text", "") if isinstance(result.get("text"), str) else ""
                n = append_document(all_documents, seed_url, result.get("category", "Campus Life"), 0, raw_text)
                if n:
                    already_processed.add(seed_url)
                    print(f"  ✓ [{result.get('category', 'Campus Life')}] → {n} chunk(s)")
                    with open(OUTPUT_FILE, "w") as f:
                        json.dump(all_documents, f, indent=2, ensure_ascii=False)

        max_links = SEED_LINKS_PER_DEPTH[0]
        if max_links > 0:
            sub_links = get_links_general(page_text, seed_url, max_links=max_links)
            new_count = 0
            for raw_url in sub_links:
                if not isinstance(raw_url, str):
                    continue
                sub_url = resolve_url(seed_url, raw_url)
                if not sub_url or sub_url in visited or is_blocked(sub_url):
                    continue
                depth1_queue.append({"url": sub_url, "seed": seed_url})
                visited.add(sub_url)
                new_count += 1
            if new_count:
                print(f"  → queued {new_count} depth-1 links")

        time.sleep(SLEEP_SECONDS)

    print(f"\nFound {len(depth1_queue)} depth-1 pages to process\n")

    # ── Step 2: depth-1 pages ─────────────────────────────────────────────────
    depth2_queue = []
    process_depth(depth1_queue, depth2_queue, 1, already_processed, visited, all_documents, SEED_LINKS_PER_DEPTH[1])
    print(f"\nFound {len(depth2_queue)} depth-2 pages to process\n")

    # ── Step 3: depth-2 pages (scrape only, no further links) ────────────────
    process_depth(depth2_queue, None, 2, already_processed, visited, all_documents, SEED_LINKS_PER_DEPTH[2])

    print(f"\nDone.")
    print(f"  Total chunks    : {len(all_documents)}")
    print(f"  Output file     : {OUTPUT_FILE}")


if __name__ == "__main__":
    run_seed_crawl()
