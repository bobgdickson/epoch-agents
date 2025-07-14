from pydantic import BaseModel
from agents import function_tool, Agent, Runner, trace
import asyncio
import os
from sqlalchemy import create_engine, Column, String, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_FILE = os.getenv("DB_FILE", "email_triage.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class EmailORM(Base):
    __tablename__ = "emails"

    message_id = Column(String, primary_key=True, index=True)
    subject = Column(String)
    sender = Column(String)
    date = Column(String)
    body = Column(Text)
    received_at = Column(String)
    processed = Column(Boolean, default=False)
    processed_at = Column(String)

Base.metadata.create_all(bind=engine)
class Email(BaseModel):
    """
    Represents an email message for triage and summarization.
    """
    message_id: str
    subject: str
    sender: str
    date: str
    body: str



class EmailList(BaseModel):
    """
    Container for a list of emails fetched for processing.
    """
    emails: list[Email]


class ReportOutput(BaseModel):
    """
    Represents the output of saving the report.
    """
    path: str
    success: bool


class ProcessedOutput(BaseModel):
    success: bool


@function_tool
def get_unprocessed_emails() -> EmailList:
    """
    Reads unprocessed emails from the local database.

    Returns:
        EmailList: Emails awaiting triage.
    """
    with SessionLocal() as session:
        emails_orm = session.query(EmailORM).filter(EmailORM.processed == False).all()
        emails = [
            Email(
                message_id=e.message_id,
                subject=e.subject,
                sender=e.sender,
                date=e.date,
                body=e.body,
            )
            for e in emails_orm
        ]
    return EmailList(emails=emails)


@function_tool
def save_report(report: str) -> ReportOutput:
    """
    Saves the markdown report to a file in the report directory.

    Args:
        report (str): The markdown-formatted report content.

    Returns:
        ReportOutput: The path and status of the saved report.
    """
    report_dir = os.getenv('REPORT_DIR', 'reports')
    os.makedirs(report_dir, exist_ok=True)
    filename = f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
    path = os.path.join(report_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(report)
    return ReportOutput(path=path, success=True)


@function_tool
def mark_emails_processed(message_ids: list[str]) -> ProcessedOutput:
    """
    Marks the given email message_ids as processed in the database.
    """
    with SessionLocal() as session:
        for mid in message_ids:
            session.query(EmailORM).filter(EmailORM.message_id == mid).update(
                {
                    EmailORM.processed: True,
                    EmailORM.processed_at: datetime.utcnow().isoformat(),
                }
            )
        session.commit()
    return ProcessedOutput(success=True)


email_triage_agent = Agent(
    name="email_triage_agent",
    instructions="""
Use get_unprocessed_emails() to retrieve all unprocessed emails.
Triage each email into categories (Critical, High, Normal, Low) with the most urgent first.
Summarize emails in each category and assemble a markdown report.
Save the report using save_report(report).
After saving, mark processed emails by calling mark_emails_processed(message_ids).
Return the output of save_report.
""",
    tools=[get_unprocessed_emails, save_report, mark_emails_processed],
    model="gpt-4.1-mini",
    output_type=ReportOutput,
)


async def run_email_triage_agent():
    """
    Execute the email_triage_agent to generate and save the email triage report.
    """
    with trace("Running email_triage_agent"):
        result = await Runner.run(email_triage_agent, None)
        print(f"Report saved: {result}")
        return result


if __name__ == "__main__":
    asyncio.run(run_email_triage_agent())