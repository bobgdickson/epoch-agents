import os
import sqlite3
import importlib

import pytest
from fastapi.testclient import TestClient

# Import the app module last, after setting DB_FILE env var
import app.app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Create a temp SQLite DB for each test
    db_file = tmp_path / 'test.db'
    monkeypatch.setenv('DB_FILE', str(db_file))
    # Reload module to pick up new DB_FILE
    importlib.reload(app_module)
    client = TestClient(app_module.app)
    return client


def test_review_endpoints_empty(client):
    # No emails in the DB => empty review list
    resp = client.get('/review')
    assert resp.status_code == 200
    assert resp.json() == []


def test_email_and_review_flow(client, tmp_path, monkeypatch):
    # Send an inbound email
    payload = {
        'message_id': 'm1',
        'subject': 'Hi',
        'sender': 'user@example.com',
        'date': '2025-07-15',
        'body': 'Hello'
    }
    resp = client.post('/email', json=payload)
    assert resp.status_code == 200
    assert resp.json() == {'success': True}

    # Still not flagged for review
    resp = client.get('/review')
    assert resp.json() == []

    # Manually tag the email for review via direct DB update
    db_file = os.getenv('DB_FILE')
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("UPDATE emails SET status = ? WHERE message_id = ?", ('2 - Review', 'm1'))
    conn.commit()
    conn.close()

    # Now /review should list it
    resp = client.get('/review')
    assert resp.status_code == 200
    arr = resp.json()
    assert isinstance(arr, list) and len(arr) == 1
    e = arr[0]
    assert e['message_id'] == 'm1'

    # /review/{id} returns the specific email
    resp = client.get('/review/m1')
    assert resp.status_code == 200
    e2 = resp.json()
    assert e2['message_id'] == 'm1'

    # Nonexistent ID -> 404
    resp = client.get('/review/doesnotexist')
    assert resp.status_code == 404