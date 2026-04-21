# University of Rochester Chatbot

> **An AI assistant that answers your questions about the University of Rochester.**

🔗 **[Try it live](https://urchatbot.sotamatsuda.com)**

---

## What It Does

Ask anything about the University of Rochester and get accurate, sourced answers in seconds.

- Academics, majors, and course requirements
- Campus life, housing, and dining
- Admissions, financial aid, and deadlines
- Research opportunities and student resources

Every answer includes a source URL so you can verify the information directly.

---

## How It Works

This chatbot is built on a **RAG (Retrieval-Augmented Generation)** pipeline — a technique that grounds AI responses in real, curated data rather than relying on the model's general knowledge alone.

```
Your question
     ↓
Expanded into 3 distinct sub-queries that resolve pronouns from the
conversation and cover different angles of the question (GPT-4o mini)
     ↓
Each query (original + 3 sub-queries) converted into a vector
(OpenAI Embeddings)
     ↓
Top 8 chunks retrieved per query from a UR knowledge base, then
deduplicated into a single candidate pool (ChromaDB)
     ↓
Reranked to the top 5 most relevant (Cohere Reranker)
     ↓
Answer generated with source citations (GPT-4o mini)
```

The chatbot also remembers the conversation — so follow-up questions like *"Can you elaborate on that?"* work naturally.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, React, Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn |
| Vector Database | ChromaDB |
| Embeddings | OpenAI `text-embedding-3-small` |
| Language Model | OpenAI `gpt-4o-mini` |
| Reranker | Cohere `rerank-multilingual-v3.0` |
| Session Logging | Supabase (PostgreSQL) |
| Hosting | Render |

---

## Project Structure

```
├── main.py            # FastAPI backend — /chat endpoint
├── query_chroma.py    # RAG pipeline (expand → embed → retrieve → rerank → generate)
├── requirements.txt   # Python dependencies
├── chroma_db/         # Vector database built from UR web content
└── frontend/
    ├── index.html     # Entry point
    ├── app.js         # React chat UI
    └── logo.png       # University of Rochester logo
```

---

*Built by [Sota Matsuda](https://sotamatsuda.com)*
