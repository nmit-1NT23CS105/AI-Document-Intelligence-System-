from io import BytesIO

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.database.session import configure_database
    from app.main import create_app

    database_path = tmp_path / "phase3.db"
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


def test_chunk_text_creates_bounded_overlapping_chunks():
    from app.ai.chunking import chunk_text

    text = " ".join(f"word{i}" for i in range(120))

    chunks = chunk_text(text, chunk_size=25, overlap=5)

    assert len(chunks) == 6
    assert all(len(chunk.text.split()) <= 25 for chunk in chunks)
    assert chunks[0].text.split()[-5:] == chunks[1].text.split()[:5]
    assert chunks[0].chunk_index == 0
    assert chunks[-1].chunk_index == 5


def test_search_returns_semantic_matches_for_authenticated_user(client):
    headers = _auth_headers(client)
    leave_response = _upload_docx(
        client,
        headers,
        "leave-policy.docx",
        "Employees may take paid leave days for vacation and personal time.",
    )
    _upload_docx(
        client,
        headers,
        "invoice.docx",
        "Invoice total is 1200 dollars and payment is due next month.",
    )

    search_response = client.post(
        "/search",
        headers=headers,
        json={"query": "holiday allowance", "limit": 3},
    )

    assert leave_response.status_code == 201
    assert search_response.status_code == 200
    results = search_response.json()["results"]
    assert results
    assert results[0]["document_id"] == leave_response.json()["id"]
    assert results[0]["filename"] == "leave-policy.docx"
    assert results[0]["score"] > 0
    assert "paid leave days" in results[0]["snippet"]


def test_search_can_be_scoped_and_returns_enriched_match_context(client):
    headers = _auth_headers(client)
    _upload_docx(
        client,
        headers,
        "leave-policy.docx",
        "Employees may take paid leave days for vacation and personal time.",
    )
    invoice_response = _upload_docx(
        client,
        headers,
        "invoice.docx",
        "Invoice number 42 has a payment due date in April. The invoice total is 1200 dollars.",
    )

    search_response = client.post(
        "/search",
        headers=headers,
        json={
            "query": "payment due date",
            "limit": 5,
            "document_id": invoice_response.json()["id"],
        },
    )

    assert search_response.status_code == 200
    results = search_response.json()["results"]
    assert results
    assert {result["document_id"] for result in results} == {invoice_response.json()["id"]}
    assert results[0]["filename"] == "invoice.docx"
    assert results[0]["category"]
    assert results[0]["file_type"] == "docx"
    assert results[0]["match_type"] in {"Exact phrase", "Keyword + semantic"}
    assert results[0]["relevance_label"] in {"High", "Medium"}
    assert {"payment", "due", "date"}.issubset(set(results[0]["highlights"]))


def test_search_returns_focused_snippet_around_matching_terms(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("CHUNK_SIZE_WORDS", "240")
    monkeypatch.setenv("CHUNK_OVERLAP_WORDS", "20")
    get_settings.cache_clear()

    headers = _auth_headers(client)
    filler_before = " ".join(f"before{i}" for i in range(80))
    filler_after = " ".join(f"after{i}" for i in range(80))
    upload_response = _upload_docx(
        client,
        headers,
        "contract.docx",
        f"{filler_before} critical renewal date is 31 March 2027 with automatic extension {filler_after}",
    )

    search_response = client.post(
        "/search",
        headers=headers,
        json={
            "query": "critical renewal date",
            "limit": 1,
            "document_id": upload_response.json()["id"],
        },
    )

    assert search_response.status_code == 200
    result = search_response.json()["results"][0]
    assert "critical renewal date" in result["snippet"]
    assert result["snippet"].startswith("...")
    assert result["snippet"].endswith("...")
    assert len(result["snippet"]) < 420
    assert result["match_type"] == "Exact phrase"


def test_search_is_user_scoped_and_delete_removes_indexed_chunks(client):
    ada_headers = _auth_headers(client, "ada@example.com")
    bob_headers = _auth_headers(client, "bob@example.com")
    uploaded = _upload_docx(
        client,
        ada_headers,
        "policy.docx",
        "Leave policy gives employees vacation days.",
    )

    bob_search = client.post(
        "/search",
        headers=bob_headers,
        json={"query": "holiday allowance", "limit": 3},
    )
    delete_response = client.delete(
        f"/document/{uploaded.json()['id']}",
        headers=ada_headers,
    )
    ada_search_after_delete = client.post(
        "/search",
        headers=ada_headers,
        json={"query": "holiday allowance", "limit": 3},
    )

    assert uploaded.status_code == 201
    assert bob_search.status_code == 200
    assert bob_search.json()["results"] == []
    assert delete_response.status_code == 204
    assert ada_search_after_delete.status_code == 200
    assert ada_search_after_delete.json()["results"] == []
