import json
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
NUM_SUBQUERIES = 3   # sub-queries generated per user question
PER_QUERY_K    = 8   # candidates fetched per (sub-)query
TOP_N          = 5   # final chunks kept after reranking

SYSTEM_PROMPT = """You are a helpful assistant for the University of Rochester.
Answer the student's question using only the provided context.
You can also add peripheral information that the user might not directly ask for, but that you think is helpful - as long as it comes from the provided context.
If the context does not contain enough information to answer, say so honestly.
Where relevant, mention the source URL so the student knows where to find more details."""

client = OpenAI()
co     = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
db     = chromadb.PersistentClient(path=CHROMA_DIR)
collection = db.get_collection(COLLECTION)


def expand_query(question: str, history: list[dict]) -> list[str]:
    system = (
        f"""Rewrite the student's question into {NUM_SUBQUERIES} short, standalone keyword search queries that together cover what the student likely wants to know. 
        Resolve all pronouns and topic references using the conversation history so every query is fully self-contained. 
        Ensure the queries target distinct angles, subtopics, or vocabulary — no two queries should share the same core keyword. 
        If the intent is ambiguous, cover the most plausible interpretations. 
        Return only a JSON object: {{"queries": ["...", "...", "..."]}}"""
    )
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": question},
    ]
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    subs = [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]
    return [question, *subs]


def embed_queries(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in response.data]


def retrieve(queries: list[str]) -> tuple[list[str], list[dict]]:
    embeddings = embed_queries(queries)
    results = collection.query(query_embeddings=embeddings, n_results=PER_QUERY_K)

    seen_ids: set[str] = set()
    docs: list[str] = []
    metadatas: list[dict] = []
    for q_ids, q_docs, q_metas in zip(results["ids"], results["documents"], results["metadatas"]):
        for cid, doc, meta in zip(q_ids, q_docs, q_metas):
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            docs.append(doc)
            metadatas.append(meta)
    return docs, metadatas


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
    queries = expand_query(question, history)
    docs, metadatas = retrieve(queries)
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
