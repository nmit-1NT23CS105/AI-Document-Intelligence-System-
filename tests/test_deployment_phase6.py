from pathlib import Path

from fastapi.testclient import TestClient


def test_health_endpoint_reports_application_and_database_status(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'health.db'}")

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "AI Document Intelligence System",
        "version": "0.1.0",
        "database": "ok",
    }


def test_docker_deployment_files_exist_with_expected_runtime_contracts():
    dockerfile = Path("Dockerfile")
    dockerignore = Path(".dockerignore")

    assert dockerfile.exists()
    assert dockerignore.exists()

    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    dockerignore_text = dockerignore.read_text(encoding="utf-8")

    assert "python:" in dockerfile_text
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile_text
    assert "EXPOSE 8000" in dockerfile_text
    assert "uvicorn app.main:app" in dockerfile_text
    assert "/health" in dockerfile_text

    assert ".venv/" in dockerignore_text
    assert "__pycache__/" in dockerignore_text
    assert "uploads/*" in dockerignore_text
    assert "chromadb/" in dockerignore_text
