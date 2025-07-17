import os
import pytest
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import epoch_agent.email_triage_agent as triage


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    # Configure an in-memory SQLite database for testing
    engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    # Monkeypatch ORM engine and session
    triage.engine = engine
    triage.SessionLocal = SessionLocal
    # Recreate schema
    triage.Base.metadata.create_all(bind=engine)
    return SessionLocal


def test_get_and_mark_unprocessed_emails(in_memory_db):
    session = in_memory_db()
    # Insert a sample unprocessed email
    orm_email = triage.EmailORM(
        message_id='id1',
        subject='Test Subject',
        sender='sender@example.com',
        date='2025-07-15',
        body='Hello world',
        received_at='2025-07-15T00:00:00'
    )
    session.add(orm_email)
    session.commit()

    # Fetch unprocessed emails
    email_list = triage.get_unprocessed_emails()
    assert len(email_list.emails) == 1
    assert email_list.emails[0].message_id == 'id1'

    # Mark the email as processed with a status tag
    status = triage.EmailStatus(message_id='id1', status='! - Bob')
    result = triage.mark_emails_processed([status])
    assert result.success

    # After processing, it should not appear in unprocessed list
    remaining = triage.get_unprocessed_emails()
    assert remaining.emails == []

    # Verify the database fields were updated
    updated = session.query(triage.EmailORM).get('id1')
    assert updated.processed
    assert updated.status == '! - Bob'
    assert updated.processed_at is not None


def test_save_report(tmp_path, monkeypatch):
    # Use a temporary directory for reports
    monkeypatch.setenv('REPORT_DIR', str(tmp_path))
    content = '# Sample Report'
    output = triage.save_report(content)
    assert output.success
    report_path = tmp_path / output.path.name
    assert report_path.exists()
    assert report_path.read_text(encoding='utf-8') == content