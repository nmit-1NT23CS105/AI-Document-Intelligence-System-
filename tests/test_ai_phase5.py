from io import BytesIO

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.database.session import configure_database
    from app.main import create_app

    database_path = tmp_path / "phase5.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1048576")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "database")
    get_settings.cache_clear()
    configure_database(f"sqlite:///{database_path}")

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()


def _auth_headers(client: TestClient, email: str = "ada@example.com") -> dict[str, str]:
    client.post(
        "/register",
        json={
            "name": email.split("@")[0].title(),
            "email": email,
            "password": "StrongPass123",
        },
    )
    response = client.post(
        "/login",
        json={"email": email, "password": "StrongPass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _docx_bytes(text: str) -> bytes:
    document = DocxDocument()
    document.add_paragraph(text)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _upload_docx(client: TestClient, headers: dict[str, str], filename: str, text: str):
    return client.post(
        "/upload",
        headers=headers,
        files={
            "file": (
                filename,
                _docx_bytes(text),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )


def test_upload_classifies_invoice_and_metadata_exposes_category(client):
    headers = _auth_headers(client)
    upload_response = _upload_docx(
        client,
        headers,
        "invoice.docx",
        "Invoice number INV-2026-009. Bill to Acme Corp. "
        "Payment is due in 30 days. Total amount due is 1200 dollars.",
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["category"] == "Invoice"

    metadata_response = client.get(f"/metadata/{uploaded['id']}", headers=headers)
    assert metadata_response.status_code == 200
    assert metadata_response.json()["category"] == "Invoice"


def test_summarize_returns_short_summary_and_key_points(client):
    headers = _auth_headers(client)
    upload_response = _upload_docx(
        client,
        headers,
        "policy.docx",
        "Employees receive 18 paid leave days every calendar year. "
        "Unused leave expires on March 31. "
        "Managers must approve leave requests before travel is booked.",
    )

    response = client.post(
        "/summarize",
        headers=headers,
        json={"document_id": upload_response.json()["id"], "max_key_points": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == upload_response.json()["id"]
    assert body["filename"] == "policy.docx"
    assert body["short_summary"] == (
        "Employees receive 18 paid leave days every calendar year. "
        "Unused leave expires on March 31."
    )
    assert body["key_points"] == [
        "Employees receive 18 paid leave days every calendar year.",
        "Unused leave expires on March 31.",
    ]


def test_summarize_skips_short_unpunctuated_heading():
    from app.ai.summarization import summarize_text

    short_summary, key_points = summarize_text(
        "Runtime QA Policy\n"
        "Employees receive 18 paid leave days every calendar year. "
        "Unused leave expires on March 31.",
        summary_sentence_count=2,
        max_key_points=3,
    )

    assert short_summary == (
        "Employees receive 18 paid leave days every calendar year. "
        "Unused leave expires on March 31."
    )
    assert key_points[0] == "Employees receive 18 paid leave days every calendar year."


def test_summarize_cannot_access_another_users_document(client):
    ada_headers = _auth_headers(client, "ada@example.com")
    bob_headers = _auth_headers(client, "bob@example.com")
    uploaded = _upload_docx(
        client,
        ada_headers,
        "report.docx",
        "Quarterly revenue increased by 12 percent.",
    )

    response = client.post(
        "/summarize",
        headers=bob_headers,
        json={"document_id": uploaded.json()["id"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
