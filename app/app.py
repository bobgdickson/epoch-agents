from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from agents import Runner
from epoch_agent.email_triage_agent import Email, ReportOutput, run_email_triage_agent, Base, EmailORM

load_dotenv()

DB_PATH = os.getenv("DB_FILE", "email_triage.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()

class InboundEmail(BaseModel):
    message_id: str
    subject: str
    sender: str
    date: str
    body: str


@app.post("/email")
def receive_email(inbound: InboundEmail):
    try:
        with SessionLocal() as session:
            email = EmailORM(
                message_id=inbound.message_id,
                subject=inbound.subject,
                sender=inbound.sender,
                date=inbound.date,
                body=inbound.body,
                received_at=datetime.utcnow().isoformat(),
            )
            session.add(email)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        print(f"Received email: {inbound.subject}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


@app.get("/review", response_model=list[Email])
def list_review_emails():
    """List emails flagged for review."""
    with SessionLocal() as session:
        emails_orm = session.query(EmailORM).filter(EmailORM.status.isnot(None)).all()
        return [
            Email(
                message_id=e.message_id,
                subject=e.subject,
                sender=e.sender,
                date=e.date,
                body=e.body,
            )
            for e in emails_orm
        ]


@app.get("/review/{message_id}", response_model=Email)
def view_review_email(message_id: str):
    """Retrieve a single email by message_id for manual review."""
    with SessionLocal() as session:
        email = (
            session.query(EmailORM)
            .filter(EmailORM.message_id == message_id, EmailORM.status.isnot(None))
            .first()
        )
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        return Email(
            message_id=email.message_id,
            subject=email.subject,
            sender=email.sender,
            date=email.date,
            body=email.body,
        )


@app.post("/process", response_model=ReportOutput)
async def process_emails():
    return await run_email_triage_agent()

@app.post("/fetch_email")
async def fetch_email():
    """Fetch emails from IMAP server."""
    from epoch_agent.services.imap_fetcher import fetch_emails
    try:
        fetch_emails()
        return {"success": True, "message": "Emails fetched successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))