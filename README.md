# University of Rochester Chatbot

An AI-powered chatbot that answers questions about the University of Rochester — academics, campus life, admissions, housing, and more.

## Demo

> Try it live: [ur-chatbot.onrender.com](https://ur-chatbot.onrender.com)

---

## How It Works

This project uses a **RAG (Retrieval-Augmented Generation)** pipeline:

1. **Embed** — the user's question is converted into a vector using OpenAI's `text-embedding-3-small`
2. **Retrieve** — the top 20 most semantically similar chunks are fetched from a local ChromaDB vector database built from UR web content
3. **Rerank** — Cohere's `rerank-multilingual-v3.0` narrows those 20 chunks down to the top 5 most relevant
4. **Generate** — the 5 chunks are passed as context to `gpt-4o-mini`, which generates a grounded answer with source URLs
5. **History** — previous messages in the session are included so the model understands follow-up questions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, React (CDN), Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn |
| Vector Database | ChromaDB (local) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Language Model | OpenAI `gpt-4o-mini` |
| Reranker | Cohere `rerank-multilingual-v3.0` |
| Hosting | Render (free tier) |

---

## Project Structure

```
├── main.py               # FastAPI app — /chat endpoint
├── query_chroma.py       # RAG pipeline (embed, retrieve, rerank, generate)
├── requirements.txt      # Python dependencies
├── chroma_db/            # Local vector database
└── frontend/
    ├── index.html        # Entry point
    ├── app.js            # React chatbot UI
    └── logo.png          # University of Rochester logo
```

---

## Running Locally

**Backend**
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
python3 -m http.server 8080
```
Then open `http://localhost:8080`.

**Environment Variables**
```
OPENAI_API_KEY=your_key
COHERE_API_KEY=your_key
```

---

## Deployment

The backend is deployed on **Render** as a Web Service:
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

The frontend is a static site served directly from the `frontend/` folder.
