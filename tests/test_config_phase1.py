from app.core.config import get_settings


def test_default_database_url_uses_local_sqlite_when_env_is_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ENV_FILE", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == "sqlite:///./dev.db"


def test_settings_can_read_database_url_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=mysql+pymysql://app_user:secret@localhost:3306/docs\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV_FILE", str(env_file))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == (
        "mysql+pymysql://app_user:secret@localhost:3306/docs"
    )
