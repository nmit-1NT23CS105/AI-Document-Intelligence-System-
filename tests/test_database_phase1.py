from app.database.models import Base


def test_phase_one_database_models_match_prompt_relationships():
    tables = Base.metadata.tables

    assert {"users", "documents", "chat_history"}.issubset(tables.keys())

    users = tables["users"].columns
    assert {"id", "name", "email", "password_hash"}.issubset(users.keys())
    assert users["email"].unique is True

    documents = tables["documents"].columns
    assert {
        "id",
        "user_id",
        "filename",
        "filepath",
        "file_type",
        "category",
        "upload_date",
    }.issubset(documents.keys())

    chat_history = tables["chat_history"].columns
    assert {
        "id",
        "user_id",
        "document_id",
        "question",
        "answer",
        "created_at",
    }.issubset(chat_history.keys())

    assert documents["user_id"].foreign_keys
    assert chat_history["user_id"].foreign_keys
    assert chat_history["document_id"].foreign_keys
