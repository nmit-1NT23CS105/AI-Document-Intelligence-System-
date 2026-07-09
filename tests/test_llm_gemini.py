from io import BytesIO
import json

import httpx
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.database.session import configure_database
    from app.main import create_app

    database_path = tmp_path / "gemini.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1048576")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "database")
    monkeypatch.setenv("LLM_PROVIDER", "none")
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


def test_settings_read_gemini_llm_configuration(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.15")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.llm_temperature == 0.15
    assert settings.llm_timeout_seconds == 12

    get_settings.cache_clear()


def test_gemini_client_posts_interactions_request_and_extracts_output_text():
    from app.ai.llm import GeminiLLMClient

    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        payload = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "test-key"
        assert payload["model"] == "gemini-3.5-flash"
        assert payload["input"] == "User prompt"
        assert payload["system_instruction"] == "System prompt"
        assert payload["generation_config"] == {"temperature": 0.2}
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "text", "text": "Grounded Gemini answer."}
                        ],
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = GeminiLLMClient(
            api_key="test-key",
            model_name="gemini-3.5-flash",
            base_url="https://example.test/v1beta/interactions",
            temperature=0.2,
            timeout_seconds=5,
            http_client=http_client,
        )

        answer = client.generate_text("System prompt", "User prompt")

    assert answer == "Grounded Gemini answer."
    assert len(seen_requests) == 1
    assert seen_requests[0].method == "POST"
    assert str(seen_requests[0].url) == "https://example.test/v1beta/interactions"


def test_chat_uses_llm_answer_when_client_is_available(client, monkeypatch):
    class FakeLLMClient:
        def __init__(self) -> None:
            self.prompts: list[tuple[str, str]] = []

        def generate_text(self, system_prompt: str, user_prompt: str) -> str:
            self.prompts.append((system_prompt, user_prompt))
            return "Gemini answer: employees receive 18 paid leave days."

    fake_client = FakeLLMClient()
    monkeypatch.setattr("app.services.chat_service.get_llm_client", lambda: fake_client)
    headers = _auth_headers(client)
    upload_response = _upload_docx(
        client,
        headers,
        "leave-policy.docx",
        "Employees receive 18 paid leave days every calendar year.",
    )

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "question": "How many paid leave days do employees receive?",
            "document_id": upload_response.json()["id"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Gemini answer: employees receive 18 paid leave days."
    assert body["citations"][0]["filename"] == "leave-policy.docx"
    assert "leave-policy.docx" in fake_client.prompts[0][1]


def test_summary_uses_llm_json_when_client_is_available(client, monkeypatch):
    class FakeLLMClient:
        def generate_text(self, system_prompt: str, user_prompt: str) -> str:
            return json.dumps(
                {
                    "short_summary": "Gemini summary of the policy.",
                    "key_points": [
                        "Employees receive 18 paid leave days.",
                        "Managers approve leave requests.",
                    ],
                }
            )

    monkeypatch.setattr("app.services.summary_service.get_llm_client", lambda: FakeLLMClient())
    headers = _auth_headers(client)
    upload_response = _upload_docx(
        client,
        headers,
        "policy.docx",
        "Employees receive 18 paid leave days every calendar year. "
        "Managers must approve leave requests before travel is booked.",
    )

    response = client.post(
        "/summarize",
        headers=headers,
        json={"document_id": upload_response.json()["id"], "max_key_points": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["short_summary"] == "Gemini summary of the policy."
    assert body["key_points"] == [
        "Employees receive 18 paid leave days.",
        "Managers approve leave requests.",
    ]
