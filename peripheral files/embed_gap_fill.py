import json
import os
import time
import hashlib
import chromadb
from openai import OpenAI

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(SCRIPT_DIR, "..", "json data", "gap_fill_data.json")
CHROMA_DIR  = os.path.join(SCRIPT_DIR, "..", "chroma_db")

EMBED_MODEL = "text-embedding-3-small"
COLLECTION  = "ur_knowledge"
BATCH_SIZE  = 100


client = OpenAI()
db     = chromadb.PersistentClient(path=CHROMA_DIR)


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        documents = json.load(f)
    print(f"Loaded {len(documents)} chunks from {os.path.basename(INPUT_FILE)}")

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

    # Get existing collection — never delete it (upsert into preexisting DB)
    collection = db.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Collection '{COLLECTION}' has {collection.count()} existing vectors")

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
            doc_id      = hashlib.md5(f"{url}__chunk_{chunk_index}".encode()).hexdigest()
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

        # upsert — safe to re-run; updates existing, inserts new
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        embedded += len(batch)
        print(f"  Upserted {embedded}/{total}")

        if batch_start + BATCH_SIZE < total:
            time.sleep(0.5)

    print(f"\nDone. {embedded} chunks added to '{COLLECTION}'")
    print(f"Collection now has {collection.count()} total vectors")


if __name__ == "__main__":
    main()
