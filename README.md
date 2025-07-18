# epoch-agents

## Email Triage Agent

The repository provides a FastAPI service to receive inbound email posts, store them in a local SQLite DB, and an endpoint to invoke an OpenAI Agents SDK workflow to triage and summarize new messages into a markdown report.

### Environment Variables

`DB_FILE` (optional, default: email_triage.db): Path to the local SQLite database
`REPORT_DIR` (optional, default: reports): Directory to save markdown reports

### Usage

```bash
# start the FastAPI server (handles inbound email and processing)
uvicorn app.app:app --reload --port 8000

# POST email data to /email (Cloudflare Worker will handle forwarding)
curl -X POST http://localhost:8000/email \
  -H "Content-Type: application/json" \
  -d '{"message_id":"<id>","subject":"...","sender":"...","date":"...","body":"..."}'

# trigger the email triage and report generation
curl -X POST http://localhost:8000/process
```

### Manual Review

```bash
# manually retag emails flagged "2 - Review"
python -m epoch_agent.manual_review
```

### IMAP Fetcher

```bash
# fetch new unseen emails (up to one week old) via IMAP into the database
# mailbox is opened read-only so messages are not marked or deleted
# captures HTML body and stores attachments up to IMAP_ATTACHMENT_MAX_SIZE (default 1MB)
python -m epoch_agent.imap_fetcher
```