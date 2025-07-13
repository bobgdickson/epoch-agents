from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import sqlite3
from datetime import datetime

from agents import Runner
from epoch_agent.email_triage_agent import ReportOutput, run_email_triage_agent

load_dotenv()

DB_PATH = os.getenv("DB_FILE", "email_triage.db")

app = FastAPI()

@app.on_event("startup")
def on_startup():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS emails (
            message_id TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            date TEXT,
            body TEXT,
            received_at TEXT,
            processed INTEGER DEFAULT 0,
            processed_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class InboundEmail(BaseModel):
    message_id: str
    subject: str
    sender: str
    date: str
    body: str


@app.post("/email")
def receive_email(inbound: InboundEmail):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO emails (
                message_id, subject, sender, date, body, received_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                inbound.message_id,
                inbound.subject,
                inbound.sender,
                inbound.date,
                inbound.body,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"success": True}


@app.post("/process", response_model=ReportOutput)
async def process_emails():
    return await run_email_triage_agent()