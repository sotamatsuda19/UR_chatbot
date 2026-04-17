import json
import os
import time
import hashlib
import chromadb
from openai import OpenAI

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_FILES  = {
    "academic":    os.path.join(SCRIPT_DIR, "unified_ur_data.json"),
    "campus_life": os.path.join(SCRIPT_DIR, "campus_life_data.json"),
    "gap_fill":    os.path.join(SCRIPT_DIR, "gap_fill_data.json"),
}
CHROMA_DIR   = os.path.join(SCRIPT_DIR, "chroma_db")

EMBED_MODEL = "text-embedding-3-small"
COLLECTION  = "ur_knowledge"
BATCH_SIZE  = 100   # OpenAI allows up to 2048 per call; 100 is safe & trackable


client = OpenAI()
db     = chromadb.PersistentClient(path=CHROMA_DIR)


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main():
    documents = []
    for source, path in INPUT_FILES.items():
        if not os.path.exists(path):
            print(f"  WARNING: {os.path.basename(path)} not found — skipping")
            continue
        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)
        for chunk in chunks:
            chunk["_source"] = source
        documents.extend(chunks)
        print(f"Loaded {len(chunks):>5} chunks from {os.path.basename(path)}")
    print(f"Total: {len(documents)} chunks")

    if not documents:
        print("No documents to embed. Exiting.")
        return

    # Deduplicate by ID (url + chunk_index) — last occurrence wins
    seen = {}
    for doc in documents:
        url         = doc.get("url") or ""
        chunk_index = doc.get("chunk_index") or 0
        doc_id      = hashlib.md5(f"{url}__chunk_{chunk_index}".encode()).hexdigest()
        seen[doc_id] = doc
    duplicates = len(documents) - len(seen)
    if duplicates:
        print(f"Removed {duplicates} duplicate(s) — {len(seen)} unique chunks remain")
    documents = list(seen.values())

    collection = db.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    existing_ids = set(collection.get(include=[])["ids"])
    if existing_ids:
        before = len(documents)
        documents = [d for d in documents
                     if hashlib.md5(f"{d.get('url') or ''}__chunk_{d.get('chunk_index') or 0}".encode()).hexdigest()
                     not in existing_ids]
        print(f"Skipping {before - len(documents)} chunk(s) already in collection — {len(documents)} new to embed")

    if not documents:
        print("Nothing new to embed. Exiting.")
        return

    total    = len(documents)
    embedded = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = documents[batch_start: batch_start + BATCH_SIZE]

        ids       = []
        texts     = []
        metadatas = []

        for doc in batch:
            text = doc.get("text") or ""
            if not text.strip():
                continue
            url         = doc.get("url") or ""
            chunk_index = doc.get("chunk_index") or 0
            raw         = f"{url}__chunk_{chunk_index}"
            doc_id      = hashlib.md5(raw.encode()).hexdigest()
            ids.append(doc_id)
            texts.append(text)
            metadatas.append({
                "url":          url,
                "department":   doc.get("department") or "",
                "content_type": doc.get("content_type") or "",
            })

        if not texts:
            continue

        embeddings = embed_batch(texts)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        embedded += len(batch)
        print(f"  Embedded {embedded}/{total}")

        # Avoid hitting rate limits on large datasets
        if batch_start + BATCH_SIZE < total:
            time.sleep(0.5)

    print(f"\nDone. {embedded} chunks stored in ChromaDB at: {CHROMA_DIR}")
    print(f"Collection: '{COLLECTION}'")


if __name__ == "__main__":
    main()
