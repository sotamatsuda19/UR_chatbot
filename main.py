from fastapi import FastAPI, HTTPException, Request
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import psycopg2
import os
import json
from datetime import datetime

from query_chroma import ask

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []
    session_id: str = ""


@app.post("/chat")
@limiter.limit("10/minute")
def chat(request: Request, body: ChatRequest):
    answer = ask(body.question, body.history)

    if body.session_id:
        try:
            messages = body.history + [
                {"role": "user",      "text": body.question},
                {"role": "assistant", "text": answer},
            ]
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO sessions (session_id, messages, started_at, last_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                SET messages = EXCLUDED.messages,
                    last_active = EXCLUDED.last_active
            """, (body.session_id, json.dumps(messages), datetime.utcnow(), datetime.utcnow()))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB error: {e}")

    return {"answer": answer}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, host="0.0.0.0")
