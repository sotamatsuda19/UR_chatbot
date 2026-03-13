import json
import re
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(SCRIPT_DIR, "campus_life_data.json")
OUTPUT_FILE = INPUT_FILE  # overwrite in place

CHUNK_SIZE    = 1500
CHUNK_OVERLAP = 300
MIN_CHARS     = 100


# ─────────────────────────────────────────────────────────────────────────────
# Cleaning
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    # Dynamic hours content
    text = re.sub(r"(?:Spring|Fall|Winter|Summer) Standard Hours of Operation.*?\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"All dining locations are currently (?:open|closed)\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"What'?s Open Now.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{1,2}:\d{2}\s?(?:am|pm|AM|PM)", "", text)
    
    text = re.sub(r"The information contained on this dining website.*?dining manager on duty\.", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(?:Location|Address):?\s?University of Rochester.*?\d{5}-\d{4}", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"Phone:?\s?\(?\d{3}\)?\s?\d{3}-\d{4}", "", text)
    text = re.sub(r"Email:?\s?\S+@\S+", "", text)
    text = re.sub(r"Lorem ipsum.*?(\.|\n)", "", text, flags=re.IGNORECASE)
    # "Upcoming Events/Opportunities" are time-specific and stale quickly — remove
    # "Latest news" is kept because it often contains policy updates (e.g. FA deadlines)
    text = re.sub(r"(?:Upcoming Events|Upcoming Opportunities).*?(?=\n\n|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\b\d{10}\b", "", text)
    
    text = re.sub(r"\b(?:noon|midnight)\b", "", text, flags=re.IGNORECASE)

    # Navigation & accessibility noise
    text = re.sub(r"Skip to (?:Content|Navigation)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Accessibility Preferences", "", text, flags=re.IGNORECASE)
    text = re.sub(r"High Contrast", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Font Size.*", "", text, flags=re.IGNORECASE)

    # "Helpful Links" / "Resources for" navigation blocks — pure nav noise
    text = re.sub(r"Helpful [Ll]inks?:?.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"Resources for\n(?:\*[^\n]*\n)+", "", text)

    # Markdown: convert [link text](url) → link text (keep the label, drop the URL)
    text = re.sub(r"\[([^\]]+)\]\((?!mailto)[^)]+\)", r"\1", text)

    # Markdown: remove mailto links entirely (no useful display text for chatbot)
    text = re.sub(r"\[.*?\]\(mailto:[^\)]*\)", "", text)
    
    text = re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", text)
    
    text = re.sub(
        r"^[A-Z][^.\n]{10,100}\?\s*$",
        "",
        text,
        flags=re.MULTILINE
    )
    
    text = re.sub(r"^\s*[\*\-]\s+", "", text, flags=re.MULTILINE)
    
    text = re.sub(
        r"^.*?\|\s*.*?\|\s*University of Rochester.*$",
        "",
        text,
        flags=re.MULTILINE
    )

    # Markdown: strip bold/italic markers but keep the text
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = re.sub(
        r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "",
        text
    )
    
    text = re.sub(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\s*\|\s*\d{1,2}:\d{2}\s*(?:am|pm)",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Markdown: strip header markers (## Title → Title)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Standalone raw URLs (lines that are just a URL or "Label: https://...")
    text = re.sub(r"https?://\S+", "", text)

    # Structural noise: long dividers and empty table rows
    text = re.sub(r"[-=]{3,}", "", text)
    text = re.sub(r"(\|\s*)+\|", "", text)

    # Alphabet directory indexes like A[B]C[D]...
    text = re.sub(r"(?:[A-Z]\[?[A-Z]?\]?\s*){5,}", "", text)

    # Markdown image tags
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Collapse leftover bullet lines that became empty after link stripping
    text = re.sub(r"^[\*\-]\s*$", "", text, flags=re.MULTILINE)

    # Normalize whitespace: 3+ newlines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    # space before punctuation
    text = re.sub(r"\s+([.,:;])", r"\1", text)

    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Chunking  (identical logic to process_for_rag.py)
# ─────────────────────────────────────────────────────────────────────────────

def snap_to_boundary(text: str, pos: int) -> int:
    """Advance pos forward to the next whitespace character (word boundary)."""
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
# Main
# ─────────────────────────────────────────────────────────────────────────────

def process():
    with open(INPUT_FILE, encoding="utf-8") as f:
        documents = json.load(f)

    print(f"Loaded {len(documents)} documents")

    processed = []
    skipped   = 0
    chunked   = 0

    for doc in documents:
        text = doc.get("text", "") or ""

        # 1. Clean
        text = clean_text(text)

        # 2. Filter
        if len(text) < MIN_CHARS:
            skipped += 1
            continue

        # Base metadata (everything except text)
        meta = {k: v for k, v in doc.items() if k != "text"}

        # 3. Chunk if long enough, otherwise keep as-is
        if len(text) >= 1500:
            chunks = split_into_chunks(text)
            for idx, chunk in enumerate(chunks):
                entry = dict(meta)
                entry["text"]        = chunk
                entry["chunk_index"] = idx
                entry["chunk_total"] = len(chunks)
                processed.append(entry)
            chunked += 1
        else:
            entry = dict(meta)
            entry["text"] = text
            processed.append(entry)

    print(f"Skipped (too short): {skipped}")
    print(f"Chunked documents  : {chunked}")
    print(f"Output entries     : {len(processed)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)

    print(f"Saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    process()
