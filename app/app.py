from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import sqlite3
from datetime import datetime

from agents import Runner
from epoch_agent.email_triage_agent import Email, ReportOutput, run_email_triage_agent

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
            processed_at TEXT,
            status TEXT
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


@app.get("/review", response_model=list[Email])
def list_review_emails():
    """List emails flagged for manual review (status == '2 - Review')."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT message_id, subject, sender, date, body FROM emails WHERE status = ?",
            ("2 - Review",),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [Email(message_id=r[0], subject=r[1], sender=r[2], date=r[3], body=r[4]) for r in rows]


@app.get("/review/{message_id}", response_model=Email)
def view_review_email(message_id: str):
    """Retrieve a single email by message_id for manual review."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT message_id, subject, sender, date, body FROM emails WHERE message_id = ?",
            (message_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    return Email(message_id=row[0], subject=row[1], sender=row[2], date=row[3], body=row[4])


@app.post("/process", response_model=ReportOutput)
async def process_emails():
    return await run_email_triage_agent()