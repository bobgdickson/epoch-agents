from pydantic import BaseModel
from agents import function_tool, Agent, Runner, trace
import asyncio
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
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
    db_path = os.getenv("DB_FILE", "email_triage.db")
    conn = sqlite3.connect(db_path)
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
    cur.execute(
        "SELECT message_id, subject, sender, date, body FROM emails WHERE processed=0"
    )
    rows = cur.fetchall()
    conn.close()
    emails = [
        Email(
            message_id=r[0],
            subject=r[1],
            sender=r[2],
            date=r[3],
            body=r[4],
        )
        for r in rows
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
    db_path = os.getenv("DB_FILE", "email_triage.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for mid in message_ids:
        cur.execute(
            "UPDATE emails SET processed=1, processed_at=? WHERE message_id=?",
            (datetime.utcnow().isoformat(), mid),
        )
    conn.commit()
    conn.close()
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