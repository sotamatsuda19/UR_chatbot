import os
import re
from collections import Counter

import chromadb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(SCRIPT_DIR, "..", "chroma_db")
COLLECTION = "ur_knowledge"
BATCH_SIZE = 500

UNDERGRAD_PATTERNS = [
    r"/undergraduate(/|\.|$)",
    r"/undergrad(/|\.|$)",
    r"/ugrad(/|\.|$)",
    r"/college/(?!gradstudies(/|$))",
    r"/admissions/apply",
    r"/admissions/undergraduate",
    r"/admissions/first-year",
    r"/admissions/transfer",
]

GRAD_PATTERNS = [
    r"/graduate(/|\.|$)",
    r"/grad(/|\.|$)",
    r"/phd(/|\.|$)",
    r"/mba(/|\.|$|-)",
    r"/ms-",
    r"/ma/",
    r"/master-",
    r"/masters(/|\.|$)",
    r"/doctoral",
    r"/postdoc",
    r"simon\.rochester\.edu/programs/",
    r"warner\.rochester\.edu",
    r"son\.rochester\.edu",
    r"urmc\.rochester\.edu",
    r"rochester\.edu/medicine",
    r"/gradstudies",
]


def classify(url: str) -> str:
    if not url:
        return "both"
    u = url.lower()

    for p in UNDERGRAD_PATTERNS:
        if re.search(p, u):
            return "undergrad"

    for p in GRAD_PATTERNS:
        if re.search(p, u):
            return "grad"

    return "both"


def main():
    db = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = db.get_collection(COLLECTION)
    total = collection.count()
    print(f"Total chunks in collection: {total}")

    tallies = Counter()
    processed = 0
    offset = 0

    while offset < total:
        batch = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["metadatas"],
        )
        ids = batch["ids"]
        metadatas = batch["metadatas"]
        if not ids:
            break

        new_metadatas = []
        for meta in metadatas:
            url = meta.get("url", "")
            audience = classify(url)
            new_meta = {**meta, "audience": audience}
            new_metadatas.append(new_meta)
            tallies[audience] += 1

        collection.update(ids=ids, metadatas=new_metadatas)

        processed += len(ids)
        offset += BATCH_SIZE
        print(f"  Tagged {processed}/{total}")

    print("\nDone. Audience distribution:")
    for label in ("undergrad", "grad", "both"):
        print(f"  {label:10s} {tallies[label]:>6d}")


if __name__ == "__main__":
    main()
