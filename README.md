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
Converted into a vector (OpenAI Embeddings)
     ↓
Top 20 relevant chunks retrieved from a UR knowledge base (ChromaDB)
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
├── query_chroma.py    # RAG pipeline (embed → retrieve → rerank → generate)
├── requirements.txt   # Python dependencies
├── chroma_db/         # Vector database built from UR web content
└── frontend/
    ├── index.html     # Entry point
    ├── app.js         # React chat UI
    └── logo.png       # University of Rochester logo
```

---

*Built by [Sota Matsuda](https://sotamatsuda.com)*
