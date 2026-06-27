from fastapi.testclient import TestClient


def test_frontend_shell_is_served_from_root(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'frontend.db'}")

    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "AI Document Intelligence System" in response.text
    assert 'id="login-form"' in response.text
    assert 'id="register-form"' in response.text
    assert 'data-view="dashboard"' in response.text
    assert 'data-view="documents"' in response.text
    assert 'data-work-tab="search"' in response.text
    assert 'data-work-tab="chat"' in response.text
    assert 'data-work-tab="summary"' in response.text
    assert "/static/css/app.css" in response.text
    assert "/static/js/app.js" in response.text


def test_frontend_static_assets_are_available(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'frontend_assets.db'}")

    with TestClient(create_app()) as client:
        css_response = client.get("/static/css/app.css")
        js_response = client.get("/static/js/app.js")

    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
    assert "@media" in css_response.text
    assert js_response.status_code == 200
    assert "async function apiRequest" in js_response.text
    assert "/register" in js_response.text
    assert "/upload" in js_response.text
    assert "/search" in js_response.text
    assert "/chat" in js_response.text
    assert "/summarize" in js_response.text


def test_frontend_exposes_advanced_document_workspace_controls(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'advanced_frontend.db'}")

    with TestClient(create_app()) as client:
        html_response = client.get("/")
        js_response = client.get("/static/js/app.js")

    assert html_response.status_code == 200
    assert 'id="global-query"' in html_response.text
    assert 'id="upload-dropzone"' in html_response.text
    assert 'id="extraction-health"' in html_response.text
    assert 'id="document-filter"' in html_response.text
    assert 'id="chat-citations"' in html_response.text
    assert 'id="summary-keypoints"' in html_response.text

    assert "function setBusy" in js_response.text
    assert "function renderExtractionHealth" in js_response.text


def test_frontend_consolidates_ai_tools_and_hides_auth_forms_by_default(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'consolidated_frontend.db'}")

    with TestClient(create_app()) as client:
        html_response = client.get("/")
        js_response = client.get("/static/js/app.js")

    html = html_response.text
    js = js_response.text

    assert 'data-view="search"' not in html
    assert 'data-view="chat"' not in html
    assert 'data-view="summary"' not in html
    assert 'id="activity-feed"' not in html
    assert 'class="panel activity-panel"' not in html

    assert 'id="auth-dialog" class="auth-dialog hidden"' in html
    assert 'id="account-button"' in html
    assert 'class="button danger hidden" id="logout-button"' in html
    assert '>Logout</button>' in html
    assert '<section class="auth-panel"' not in html

    assert 'id="upload-file" type="file" multiple' in html
    assert 'id="selected-files-list"' in html
    assert 'id="chat-thread"' in html
    assert 'id="chat-scope-note"' in html
    assert 'id="summary-insights"' in html
    assert 'id="summary-actions"' in html

    assert "async function uploadSelectedFiles" in js
    assert "function renderSelectedFiles" in js
    assert "function renderChatAnswer" in js
    assert "function renderSummary" in js
    assert "function renderActivity" not in js


def test_frontend_ai_workbench_has_professional_search_chat_summary_controls(tmp_path):
    from app.database.session import configure_database
    from app.main import create_app

    configure_database(f"sqlite:///{tmp_path / 'professional_ai_workbench.db'}")

    with TestClient(create_app()) as client:
        html_response = client.get("/")
        js_response = client.get("/static/js/app.js")

    html = html_response.text
    js = js_response.text

    assert 'id="search-document"' in html
    assert 'id="search-category-filter"' in html
    assert 'id="search-sort"' in html
    assert 'id="search-stats"' in html
    assert 'id="search-results-header"' in html

    assert 'id="chat-mode"' in html
    assert 'id="chat-clear"' in html
    assert 'id="chat-citation-panel"' in html
    assert 'id="chat-copy"' in html

    assert 'id="summary-format"' in html
    assert 'id="summary-copy"' in html
    assert 'id="summary-outline"' in html
    assert 'id="summary-status-note"' in html
    assert "<dt>Format</dt><dd>Executive brief</dd>" in html
    assert "<dt>Mode</dt><dd>Balanced</dd>" not in html

    assert "function renderSearchResults" in js
    assert "function renderChatCitations" in js
    assert "function clearChatThread" in js
    assert "function renderSummaryInsights" in js
    assert "function copyTextToClipboard" in js
