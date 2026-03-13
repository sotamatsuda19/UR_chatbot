import json
import re
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(SCRIPT_DIR, "academic_info.json")
OUTPUT_FILE = INPUT_FILE  # overwrite in place

CHUNK_SIZE    = 1500
CHUNK_OVERLAP = 300
MIN_CHARS     = 100


# ─────────────────────────────────────────────────────────────────────────────
# Cleaning
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    # Dynamic info
    text = re.sub(r"What'?s Open Now.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{1,2}:\d{2}\s?(?:am|pm|AM|PM)", "", text)

    # Navigation & accessibility noise
    text = re.sub(r"Skip to (?:Content|Navigation)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Accessibility Preferences", "", text, flags=re.IGNORECASE)
    text = re.sub(r"High Contrast", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Font Size.*", "", text, flags=re.IGNORECASE)

    # Structural noise: long dividers
    text = re.sub(r"[-=]{3,}", "", text)

    # Empty table rows (pipes with only spaces/pipes)
    text = re.sub(r"(\|\s*)+\|", "", text)

    # Alphabet directory indexes like A[B]C[D]...
    text = re.sub(r"(?:[A-Z]\[?[A-Z]?\]?\s*){5,}", "", text)

    # Markdown image tags
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Standalone mailto links
    text = re.sub(r"\[.*?\]\(mailto:[^\)]*\)", "", text)

    # Normalize whitespace: 3+ newlines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────

def snap_to_boundary(text: str, pos: int) -> int:
    """Advance pos forward to the next whitespace character (word boundary)."""
    match = re.search(r"\s", text[pos:])
    if match:
        return pos + match.start() + 1
    return pos  # no whitespace found, keep as-is


def split_into_chunks(text: str) -> list[str]:
    """
    Split text into ~CHUNK_SIZE chunks with CHUNK_OVERLAP overlap.
    Both chunk ends and overlap start positions are snapped to semantic
    boundaries (newline or period) so no chunk starts or ends mid-word.
    """
    chunks = []
    start  = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))

        if end < len(text):
            # Snap end backward to a semantic boundary in the last 200 chars
            window = text[max(start, end - 200): end]
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

        # Overlap start: go back CHUNK_OVERLAP chars, then snap forward to a
        # clean word boundary so the next chunk never begins mid-word.
        overlap_start = end - CHUNK_OVERLAP
        start = snap_to_boundary(text, max(overlap_start, 0))

        # Safety: if snapping moved us past end, just continue from end
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
