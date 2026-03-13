import os
import chromadb
import cohere
from openai import OpenAI

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR    = os.path.join(SCRIPT_DIR, "chroma_db")
EMBED_MODEL   = "text-embedding-3-small"
CHAT_MODEL    = "gpt-4o-mini"
RERANK_MODEL  = "rerank-multilingual-v3.0"
COLLECTION    = "ur_knowledge"
TOP_K         = 20   # candidates fetched from ChromaDB
TOP_N         = 5    # final chunks kept after reranking

SYSTEM_PROMPT = """You are a helpful assistant for the University of Rochester.
Answer the student's question using only the provided context.
If the context does not contain enough information to answer, say so honestly.
Where relevant, mention the source URL so the student knows where to find more details."""

client = OpenAI()
co     = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
db     = chromadb.PersistentClient(path=CHROMA_DIR)
collection = db.get_collection(COLLECTION)


def embed_query(text: str) -> list[float]:
    response = client.embeddings.create(model=EMBED_MODEL, input=[text])
    return response.data[0].embedding


def retrieve(question: str) -> tuple[list[str], list[dict]]:
    embedding = embed_query(question)
    results   = collection.query(query_embeddings=[embedding], n_results=TOP_K)
    return results["documents"][0], results["metadatas"][0]


def rerank(question: str, docs: list[str], metadatas: list[dict]) -> tuple[list[str], list[dict]]:
    response = co.rerank(
        model=RERANK_MODEL,
        query=question,
        documents=docs,
        top_n=TOP_N,
    )
    reranked_docs      = [docs[r.index]      for r in response.results]
    reranked_metadatas = [metadatas[r.index] for r in response.results]
    return reranked_docs, reranked_metadatas


def build_context(docs: list[str], metadatas: list[dict]) -> str:
    chunks = []
    for doc, meta in zip(docs, metadatas):
        url = meta.get("url", "")
        chunks.append(f"[Source: {url}]\n{doc}")
    return "\n\n---\n\n".join(chunks)


def ask(question: str, history: list[dict] = []) -> str:
    docs, metadatas = retrieve(question)
    docs, metadatas = rerank(question, docs, metadatas)
    context = build_context(docs, metadatas)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
    )

    answer = response.choices[0].message.content
    return answer


if __name__ == "__main__":
    print("UR Chatbot — type 'quit' to exit\n")
    while True:
        question = input("Question: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        ask(question)
