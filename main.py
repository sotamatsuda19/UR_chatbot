from fastapi import FastAPI, HTTPException
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import os
import json
from datetime import datetime

from query_chroma import ask


app = FastAPI()

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
def chat(request: ChatRequest):
    answer = ask(request.question, request.history)

    if request.session_id:
        try:
            messages = request.history + [
                {"role": "user",      "text": request.question},
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
            """, (request.session_id, json.dumps(messages), datetime.utcnow(), datetime.utcnow()))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB error: {e}")

    return {"answer": answer}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, host="0.0.0.0")
