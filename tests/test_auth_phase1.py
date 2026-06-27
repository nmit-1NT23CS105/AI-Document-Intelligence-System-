from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    database_path = tmp_path / "phase1.db"
    configure_database(f"sqlite:///{database_path}")

    with TestClient(create_app()) as test_client:
        yield test_client


def test_register_creates_user_without_exposing_password(client):
    response = client.post(
        "/register",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client):
    payload = {
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "password": "StrongPass123",
    }

    first_response = client.post("/register", json=payload)
    second_response = client.post("/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Email is already registered"


def test_login_returns_bearer_token_and_rejects_invalid_password(client):
    client.post(
        "/register",
        json={
            "name": "Katherine Johnson",
            "email": "katherine@example.com",
            "password": "StrongPass123",
        },
    )

    login_response = client.post(
        "/login",
        json={"email": "katherine@example.com", "password": "StrongPass123"},
    )
    bad_password_response = client.post(
        "/login",
        json={"email": "katherine@example.com", "password": "WrongPass123"},
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 40
    assert bad_password_response.status_code == 401
    assert bad_password_response.json()["detail"] == "Invalid email or password"


def test_current_user_dependency_accepts_valid_jwt_and_rejects_expired_token(
    tmp_path,
):
    from app.auth.dependencies import get_current_user
    from app.auth.security import create_access_token, hash_password
    from app.database.models import User
    from app.database.session import SessionLocal, configure_database, init_db

    database_path = tmp_path / "auth_dependency.db"
    configure_database(f"sqlite:///{database_path}")
    init_db()

    with SessionLocal() as session:
        user = User(
            name="Mary Jackson",
            email="mary@example.com",
            password_hash=hash_password("StrongPass123"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        valid_token = create_access_token(subject=str(user.id))
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token,
        )

        current_user = get_current_user(credentials=credentials, db=session)

        expired_token = create_access_token(
            subject=str(user.id),
            expires_delta=timedelta(seconds=-1),
            now=datetime.now(UTC),
        )
        expired_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=expired_token,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=expired_credentials, db=session)

    assert current_user.email == "mary@example.com"
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
