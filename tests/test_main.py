import pytest
from fastapi.testclient import TestClient
import os
import time

DB_TEST_PATH = "./data/test_events.db"

@pytest.fixture(scope="session", autouse=True)
def manage_test_db():
    if os.path.exists(DB_TEST_PATH):
        os.remove(DB_TEST_PATH)
    from src import database
    database.DB_PATH = DB_TEST_PATH
    yield
    if os.path.exists(DB_TEST_PATH):
        os.remove(DB_TEST_PATH)

@pytest.fixture(scope="session")
def client(manage_test_db):
    from src.main import app
    with TestClient(app) as test_client:
        yield test_client

def wait_for_consumer(timeout=1.5):
    time.sleep(timeout)

def test_read_stats_initial(client):
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 0
    assert data["unique_processed"] == 0
    assert data["duplicate_dropped"] == 0

def test_publish_single_event(client):
    response = client.post(
        "/publish",
        json={
            "topic": "test",
            "event_id": "test_001",
            "source": "pytest",
            "payload": {"data": 1}
        }
    )
    assert response.status_code == 202
    assert response.json()["message"] == "Accepted 1 event(s) for processing."
    wait_for_consumer()
    stats = client.get("/stats").json()
    assert stats["received"] == 1
    assert stats["unique_processed"] == 1

def test_deduplication(client):
    event = {
        "topic": "dedup",
        "event_id": "dedup_001",
        "source": "pytest",
        "payload": {"data": 1}
    }
    stats_before = client.get("/stats").json()
    client.post("/publish", json=event)
    client.post("/publish", json=event)
    wait_for_consumer()
    stats_after = client.get("/stats").json()
    assert stats_after["received"] == stats_before["received"] + 2
    assert stats_after["unique_processed"] == stats_before["unique_processed"] + 1
    assert stats_after["duplicate_dropped"] == stats_before["duplicate_dropped"] + 1

def test_get_events_by_topic(client):
    client.post(
        "/publish",
        json={
            "topic": "topic_a",
            "event_id": "evt_a1_new",
            "source": "pytest",
            "payload": {}
        }
    )
    client.post(
        "/publish",
        json={
            "topic": "topic_b",
            "event_id": "evt_b1_new",
            "source": "pytest",
            "payload": {}
        }
    )
    wait_for_consumer()
    response = client.get("/events?topic=topic_a")
    assert response.status_code == 200
    data = response.json()
    found = any(item["event_id"] == "evt_a1_new" for item in data)
    assert found == True
    found_b = any(item["event_id"] == "evt_b1_new" for item in data)
    assert found_b == False

def test_invalid_event_schema(client):
    response = client.post(
        "/publish",
        json={"bukan_event": "ini"}
    )
    assert response.status_code == 422
