#!/usr/bin/env python3
"""
Manual review tool for retagging emails flagged '2 - Review'.
"""
from datetime import datetime

from epoch_agent.email_triage_agent import EmailORM, SessionLocal


def review_loop():
    session = SessionLocal()
    try:
        pending = session.query(EmailORM).filter(EmailORM.status == "2 - Review").all()
        if not pending:
            print("No emails awaiting review.")
            return

        for email in pending:
            print("=" * 80)
            print(f"ID:      {email.message_id}")
            print(f"From:    {email.sender}")
            print(f"Date:    {email.date}")
            print(f"Subject: {email.subject}")
            print("-" * 80)
            print(email.body)
            print("-" * 80)
            choices = [
                "! - Bob",
                "1 - To Respond",
                "3 - Responded",
                "4 - Waiting On",
                "5 - Financials",
                "6 - Newsletters",
            ]
            while True:
                print("Choose new tag:")
                for tag in choices:
                    print(f"  {tag}")
                choice = input("Tag> ").strip()
                if choice in choices:
                    break
                print("Invalid choice; please enter one of the listed tags.")

            email.status = choice
            email.processed = True
            email.processed_at = datetime.utcnow().isoformat()
            session.commit()
            print(f"Email {email.message_id} updated to status '{choice}'.\n")
    finally:
        session.close()


if __name__ == "__main__":
    review_loop()