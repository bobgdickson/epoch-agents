#!/usr/bin/env python3
"""
IMAP fetcher to pull unseen messages into the triage database.
"""
import os
import email
from datetime import datetime, timedelta

try:
    from imapclient import IMAPClient
except ImportError:
    IMAPClient = None
from email.header import decode_header, make_header

## avoid circular import warning; defer ORM imports until function execution


def fetch_emails():
    """
    Connect to the IMAP server, fetch unseen emails, and store them in the database.
    """
    # import ORM types here to avoid import-cycle warnings
    from epoch_agent.email_triage_agent import EmailORM, AttachmentORM, SessionLocal
    if IMAPClient is None:
        print("imapclient library is required. Install with 'pip install imapclient'.")
        return
    host = os.getenv("IMAP_HOST")
    user = os.getenv("IMAP_USER")
    password = os.getenv("IMAP_PASS")
    folder = os.getenv("IMAP_FOLDER", "INBOX")
    ssl = os.getenv("IMAP_SSL", "True").lower() in ("1", "true", "yes")

    if not host or not user or not password:
        print("IMAP_HOST, IMAP_USER, and IMAP_PASS must be set in environment.")
        return

    with IMAPClient(host, ssl=ssl) as client:
        client.login(user, password)
        # Open mailbox readonly so messages are not marked or deleted
        client.select_folder(folder, readonly=True)
        # Only fetch unseen messages no older than one week
        since = (datetime.utcnow() - timedelta(days=1)).date()
        messages = client.search(["UNSEEN", "SINCE", since])
        if not messages:
            print("No new messages found within the last 1 days.")
            return
        response = client.fetch(messages, ["RFC822"])

    max_size = int(os.getenv("IMAP_ATTACHMENT_MAX_SIZE", 1024 * 1024))
    with SessionLocal() as session:
        for msgid, data in response.items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw)
            message_id = msg.get("Message-ID") or f"<{msgid}@{host}>"
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
            sender = str(make_header(decode_header(msg.get("From", ""))))
            date = msg.get("Date", "")
            text_body = None
            html_body = None
            # extract parts
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = part.get_content_disposition()
                    if ctype == "text/plain" and disp is None and text_body is None:
                        charset = part.get_content_charset() or "utf-8"
                        text_body = part.get_payload(decode=True).decode(charset, errors="replace")
                    elif ctype == "text/html" and disp is None and html_body is None:
                        charset = part.get_content_charset() or "utf-8"
                        html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                    elif disp == "attachment":
                        payload = part.get_payload(decode=True) or b""
                        if len(payload) <= max_size:
                            session.add(AttachmentORM(
                                message_id=message_id,
                                filename=part.get_filename(),
                                content_type=ctype,
                                data=payload,
                            ))
            else:
                charset = msg.get_content_charset() or "utf-8"
                text_body = msg.get_payload(decode=True).decode(charset, errors="replace")

            email_obj = EmailORM(
                message_id=message_id,
                subject=subject,
                sender=sender,
                date=date,
                body=text_body or "",
                html_body=html_body,
                received_at=datetime.utcnow().isoformat(),
            )
            session.add(email_obj)
            try:
                session.commit()
                print(f"Stored email {message_id}")
            except Exception:
                session.rollback()
                print(f"Email {message_id} already exists or failed to store.")


if __name__ == "__main__":
    fetch_emails()