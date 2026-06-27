const state = {
  token: localStorage.getItem("document_intelligence_token") || "",
  email: localStorage.getItem("document_intelligence_email") || "",
  documents: [],
  selectedDocumentId: null,
  selectedDetail: null,
  selectedFiles: [],
  documentFilter: "",
  categoryFilter: "",
  lastSearchRows: [],
  lastChatAnswer: "",
  lastSummaryText: "",
  busy: false,
};

const elements = {
  authStatus: document.getElementById("auth-status"),
  documentCount: document.getElementById("document-count"),
  metricDocuments: document.getElementById("metric-documents"),
  metricSelected: document.getElementById("metric-selected"),
  metricCategory: document.getElementById("metric-category"),
  tableCount: document.getElementById("table-count"),
  libraryCount: document.getElementById("library-count"),
  documentsTable: document.getElementById("documents-table"),
  recentDocuments: document.getElementById("recent-documents"),
  metadataList: document.getElementById("metadata-list"),
  documentText: document.getElementById("document-text"),
  documentPreview: document.getElementById("document-preview"),
  previewStatus: document.getElementById("preview-status"),
  deleteDocument: document.getElementById("delete-document"),
  searchDocument: document.getElementById("search-document"),
  searchCategoryFilter: document.getElementById("search-category-filter"),
  searchSort: document.getElementById("search-sort"),
  searchStats: document.getElementById("search-stats"),
  searchResults: document.getElementById("search-results"),
  chatDocument: document.getElementById("chat-document"),
  chatMode: document.getElementById("chat-mode"),
  summaryDocument: document.getElementById("summary-document"),
  summaryFormat: document.getElementById("summary-format"),
  toast: document.getElementById("toast"),
  uploadButton: document.getElementById("upload-button"),
  uploadFile: document.getElementById("upload-file"),
  uploadFileName: document.getElementById("upload-file-name"),
  uploadDropzone: document.getElementById("upload-dropzone"),
  selectedFilesList: document.getElementById("selected-files-list"),
  extractionHealth: document.getElementById("extraction-health"),
  queueList: document.getElementById("queue-list"),
  documentFilter: document.getElementById("document-filter"),
  categoryFilter: document.getElementById("category-filter"),
  chatAnswer: document.getElementById("chat-answer"),
  chatThread: document.getElementById("chat-thread"),
  chatCitations: document.getElementById("chat-citations"),
  chatCitationPanel: document.getElementById("chat-citation-panel"),
  chatScopeNote: document.getElementById("chat-scope-note"),
  chatCopy: document.getElementById("chat-copy"),
  summaryOutput: document.getElementById("summary-output"),
  summaryKeypoints: document.getElementById("summary-keypoints"),
  summaryInsights: document.getElementById("summary-insights"),
  summaryOutline: document.getElementById("summary-outline"),
  summaryStatusNote: document.getElementById("summary-status-note"),
  summaryCopy: document.getElementById("summary-copy"),
  authDialog: document.getElementById("auth-dialog"),
  accountButton: document.getElementById("account-button"),
  authClose: document.getElementById("auth-close"),
  logoutButton: document.getElementById("logout-button"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "Unknown";
  return new Date(value).toLocaleString();
}

function findDocument(documentId) {
  return state.documents.find((documentItem) => Number(documentItem.id) === Number(documentId));
}

function formatScore(value) {
  const score = Number(value || 0);
  if (!Number.isFinite(score) || score <= 0) return "n/a";
  return score.toFixed(score >= 10 ? 0 : 2);
}

function setSelectValue(select, value) {
  if (!select) return;
  const nextValue = String(value || "");
  select.value = [...select.options].some((option) => option.value === nextValue) ? nextValue : "";
}

function currentSelectLabel(select) {
  if (!select) return "";
  return select.options[select.selectedIndex]?.textContent || "";
}

async function copyTextToClipboard(text, successMessage = "Copied.") {
  const value = String(text || "").trim();
  if (!value) {
    showToast("Nothing to copy yet.");
    return;
  }

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
  } else {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  showToast(successMessage);
}

function fileQuality(documentItem, detail = null) {
  const textLength = detail?.extracted_text?.trim().length || 0;
  if (textLength > 1200) return { label: "High", tone: "success" };
  if (textLength > 0 || documentItem.number_of_pages) return { label: "Indexed", tone: "success" };
  return { label: "Needs OCR", tone: "warn" };
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.setTimeout(() => elements.toast.classList.remove("show"), 3200);
}

function setBusy(isBusy, label = "Working") {
  state.busy = isBusy;
  elements.uploadButton.disabled = isBusy;
  elements.uploadButton.textContent = isBusy ? label : "Upload Selected Files";
  document.querySelectorAll(".work-pane .button.primary").forEach((button) => {
    button.disabled = isBusy;
  });
}

function renderExtractionHealth() {
  if (!state.token) {
    elements.extractionHealth.textContent = "Signed out";
    elements.queueList.innerHTML = '<div class="empty-state">Login to start document intake.</div>';
    return;
  }

  if (state.busy) {
    elements.extractionHealth.textContent = "Extracting";
    return;
  }

  const count = state.documents.length;
  elements.extractionHealth.textContent = count ? `${count} indexed` : "Ready";
  elements.queueList.innerHTML = count
    ? state.documents
        .slice(0, 3)
        .map((documentItem) => {
          const quality = fileQuality(documentItem);
          return `
            <article class="queue-row">
              <span>
                <span class="row-title">${escapeHtml(documentItem.filename)}</span>
                <br>
                <span class="row-meta">${escapeHtml(documentItem.file_type.toUpperCase())} - ${escapeHtml(documentItem.category)}</span>
              </span>
              <span class="chip ${quality.tone}">${quality.label}</span>
            </article>
          `;
        })
        .join("")
    : '<div class="empty-state">No documents indexed yet.</div>';
}

async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const requestOptions = {
    method: options.method || "GET",
    headers,
  };

  if (options.formData) {
    requestOptions.body = options.formData;
  } else if (options.body) {
    headers.set("Content-Type", "application/json");
    requestOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, requestOptions);
  if (response.status === 204) {
    return null;
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

function setToken(token, email = "") {
  state.token = token;
  state.email = email || state.email;
  if (token) {
    localStorage.setItem("document_intelligence_token", token);
    localStorage.setItem("document_intelligence_email", state.email);
  } else {
    localStorage.removeItem("document_intelligence_token");
    localStorage.removeItem("document_intelligence_email");
    state.email = "";
  }
  renderAuthState();
  renderExtractionHealth();
}

function renderAuthState() {
  const signedIn = Boolean(state.token);
  elements.authStatus.textContent = signedIn ? "Signed in" : "Not signed in";
  document.getElementById("session-label").textContent = signedIn ? "Signed in" : "Account";
  document.getElementById("session-email").textContent = signedIn ? state.email : "Sign in to use documents";
  elements.accountButton.classList.toggle("hidden", signedIn);
  elements.logoutButton.classList.toggle("hidden", !signedIn);
  elements.accountButton.textContent = signedIn ? "Account" : "Login";
}

function openAuthDialog(mode = "login") {
  elements.authDialog.classList.remove("hidden");
  document.querySelector(`[data-auth-tab="${mode}"]`)?.click();
}

function closeAuthDialog() {
  elements.authDialog.classList.add("hidden");
}

function activateView(view) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === view);
  });
  document.getElementById("view-title").textContent = view.charAt(0).toUpperCase() + view.slice(1);
}

function activateWorkTab(tabName) {
  document.querySelectorAll(".work-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.workTab === tabName);
  });
  document.querySelectorAll(".work-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.workPane === tabName);
  });
}

function activateInspectorTab(tabName) {
  document.querySelectorAll(".inspector-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.inspectorTab === tabName);
  });
  document.querySelectorAll(".inspector-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.inspectorPane === tabName);
  });
}

function filteredDocuments() {
  const query = state.documentFilter.trim().toLowerCase();
  return state.documents.filter((documentItem) => {
    const matchesQuery =
      !query ||
      documentItem.filename.toLowerCase().includes(query) ||
      documentItem.category.toLowerCase().includes(query) ||
      documentItem.file_type.toLowerCase().includes(query);
    const matchesCategory = !state.categoryFilter || documentItem.category === state.categoryFilter;
    return matchesQuery && matchesCategory;
  });
}

function renderDocumentOptions() {
  const currentSearchDocument = elements.searchDocument.value;
  const currentSearchCategory = elements.searchCategoryFilter.value;
  const currentChatDocument = elements.chatDocument.value;
  const currentSummaryDocument = elements.summaryDocument.value;

  const documentOptions = ['<option value="">All documents</option>'].concat(
    state.documents.map((documentItem) => `<option value="${documentItem.id}">${escapeHtml(documentItem.filename)}</option>`)
  );
  elements.searchDocument.innerHTML = documentOptions.join("");
  elements.chatDocument.innerHTML = documentOptions.join("");
  setSelectValue(elements.searchDocument, currentSearchDocument);
  setSelectValue(elements.chatDocument, currentChatDocument);

  const summaryOptions = ['<option value="">Choose a document</option>'].concat(
    state.documents.map((documentItem) => `<option value="${documentItem.id}">${escapeHtml(documentItem.filename)}</option>`)
  );
  elements.summaryDocument.innerHTML = summaryOptions.join("");
  setSelectValue(elements.summaryDocument, currentSummaryDocument);

  const categories = [...new Set(state.documents.map((documentItem) => documentItem.category))].sort();
  const categoryOptions = ['<option value="">All categories</option>']
    .concat(categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`))
    .join("");
  elements.categoryFilter.innerHTML = categoryOptions;
  elements.searchCategoryFilter.innerHTML = categoryOptions;
  elements.categoryFilter.value = state.categoryFilter;
  setSelectValue(elements.searchCategoryFilter, currentSearchCategory);
}

function renderDocumentTable() {
  const rows = filteredDocuments();
  elements.tableCount.textContent = `${rows.length} shown`;
  elements.libraryCount.textContent = `${state.documents.length} indexed`;

  if (!rows.length) {
    elements.documentsTable.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">${state.documents.length ? "No documents match the current filter." : "No documents indexed yet."}</div>
        </td>
      </tr>
    `;
    return;
  }

  elements.documentsTable.innerHTML = rows
    .map((documentItem) => {
      const quality = fileQuality(documentItem);
      return `
        <tr class="${documentItem.id === state.selectedDocumentId ? "selected" : ""}">
          <td class="filename-cell">${escapeHtml(documentItem.filename)}</td>
          <td>${escapeHtml(documentItem.file_type.toUpperCase())}</td>
          <td><span class="chip">${escapeHtml(documentItem.category)}</span></td>
          <td>${documentItem.number_of_pages || 0}</td>
          <td><span class="chip ${quality.tone}">${quality.label}</span></td>
          <td>${escapeHtml(formatDate(documentItem.upload_date))}</td>
          <td><button class="button subtle" type="button" data-open-document="${documentItem.id}">View</button></td>
        </tr>
      `;
    })
    .join("");
}

function renderRecentDocuments() {
  const count = state.documents.length;
  elements.documentCount.textContent = `${count} document${count === 1 ? "" : "s"}`;
  elements.metricDocuments.textContent = String(count);

  if (!count) {
    elements.recentDocuments.className = "document-list empty-state";
    elements.recentDocuments.textContent = state.token ? "Upload a PDF or DOCX to begin." : "Sign in and upload documents to begin.";
    return;
  }

  elements.recentDocuments.className = "document-list";
  elements.recentDocuments.innerHTML = state.documents
    .slice(0, 8)
    .map((documentItem) => {
      const quality = fileQuality(documentItem);
      return `
        <article class="document-row">
          <span class="row-title">${escapeHtml(documentItem.filename)}</span>
          <span class="row-meta">${escapeHtml(documentItem.category)} - ${escapeHtml(documentItem.file_type.toUpperCase())} - ${documentItem.number_of_pages || 0} pages</span>
          <span><span class="chip ${quality.tone}">${quality.label}</span></span>
          <button class="button subtle" type="button" data-open-document="${documentItem.id}">Open details</button>
        </article>
      `;
    })
    .join("");
}

function renderDocuments() {
  renderDocumentOptions();
  renderDocumentTable();
  renderRecentDocuments();
  renderExtractionHealth();
}

async function loadDocuments() {
  if (!state.token) {
    state.documents = [];
    state.selectedDocumentId = null;
    state.selectedDetail = null;
    renderDocuments();
    renderEmptyInspector();
    return;
  }

  state.documents = await apiRequest("/documents");
  renderDocuments();
}

function renderEmptyInspector() {
  elements.metricSelected.textContent = "None";
  elements.metricCategory.textContent = "None";
  elements.previewStatus.textContent = "No document selected";
  elements.deleteDocument.disabled = true;
  elements.metadataList.innerHTML = "";
  elements.documentText.textContent = "Select a document to inspect extracted text.";
  elements.documentPreview.className = "document-preview empty-state";
  elements.documentPreview.textContent = "Select a document to inspect extracted content.";
}

function renderMetadata(documentItem, detail) {
  const quality = fileQuality(documentItem, detail);
  state.selectedDocumentId = documentItem.id;
  state.selectedDetail = detail;
  elements.metricSelected.textContent = documentItem.filename;
  elements.metricCategory.textContent = documentItem.category;
  elements.previewStatus.textContent = `${documentItem.file_type.toUpperCase()} - ${quality.label}`;
  elements.deleteDocument.disabled = false;
  elements.metadataList.innerHTML = `
    <dt>Name</dt><dd>${escapeHtml(documentItem.filename)}</dd>
    <dt>Type</dt><dd>${escapeHtml(documentItem.file_type.toUpperCase())}</dd>
    <dt>Category</dt><dd>${escapeHtml(documentItem.category)}</dd>
    <dt>Pages</dt><dd>${documentItem.number_of_pages || 0}</dd>
    <dt>Quality</dt><dd><span class="chip ${quality.tone}">${quality.label}</span></dd>
    <dt>Uploaded</dt><dd>${escapeHtml(formatDate(documentItem.upload_date))}</dd>
  `;

  const extractedText = detail.extracted_text || "No extracted text found.";
  elements.documentText.textContent = extractedText;
  elements.documentPreview.className = "document-preview";
  elements.documentPreview.innerHTML = `
    <div class="preview-title">
      <strong>${escapeHtml(documentItem.filename)}</strong>
      <span>${escapeHtml(documentItem.category)} - ${escapeHtml(documentItem.file_type.toUpperCase())} - ${documentItem.number_of_pages || 0} pages</span>
    </div>
    <p>${escapeHtml(extractedText.slice(0, 720))}${extractedText.length > 720 ? "..." : ""}</p>
    <span><span class="chip ${quality.tone}">${quality.label}</span></span>
  `;
  renderDocumentTable();
}

async function openDocument(documentId) {
  const detail = await apiRequest(`/document/${documentId}`);
  const documentItem = state.documents.find((item) => item.id === documentId) || detail;
  renderMetadata(documentItem, detail);
  activateView("dashboard");
  activateInspectorTab("preview");
}

function applySearchFilters(rows) {
  const selectedDocumentId = Number(elements.searchDocument.value || 0);
  const selectedCategory = elements.searchCategoryFilter.value;
  const sortMode = elements.searchSort.value;

  const enrichedRows = rows
    .map((row) => ({ row, documentItem: findDocument(row.document_id) }))
    .filter(({ row, documentItem }) => {
      const matchesDocument = !selectedDocumentId || Number(row.document_id) === selectedDocumentId;
      const rowCategory = row.category || documentItem?.category || "";
      const matchesCategory = !selectedCategory || rowCategory === selectedCategory;
      return matchesDocument && matchesCategory;
    });

  enrichedRows.sort((left, right) => {
    if (sortMode === "filename") {
      const leftName = left.row.filename || left.documentItem?.filename || "";
      const rightName = right.row.filename || right.documentItem?.filename || "";
      return leftName.localeCompare(rightName);
    }
    if (sortMode === "newest") {
      const leftDate = new Date(left.documentItem?.upload_date || 0).getTime();
      const rightDate = new Date(right.documentItem?.upload_date || 0).getTime();
      return rightDate - leftDate;
    }
    return Number(right.row.score || 0) - Number(left.row.score || 0);
  });

  return enrichedRows.map(({ row }) => row);
}

function renderSearchResults(rows = state.lastSearchRows, emptyMessage = "No matching documents found.") {
  const sourceRows = rows || [];
  const visibleRows = applySearchFilters(sourceRows);
  const totalCount = sourceRows.length;
  const scopedDocument = currentSelectLabel(elements.searchDocument) || "All documents";
  const scopedCategory = currentSelectLabel(elements.searchCategoryFilter) || "All categories";

  if (!totalCount) {
    elements.searchStats.textContent = emptyMessage;
    elements.searchResults.className = "result-list empty-state";
    elements.searchResults.textContent = emptyMessage;
    return;
  }

  elements.searchStats.textContent = `${visibleRows.length} of ${totalCount} matches - ${scopedDocument} - ${scopedCategory}`;

  if (!visibleRows.length) {
    elements.searchResults.className = "result-list empty-state";
    elements.searchResults.textContent = "No results match the selected scope or category.";
    return;
  }

  elements.searchResults.className = "result-list search-result-list";
  elements.searchResults.innerHTML = visibleRows
    .map((row) => {
      const documentItem = findDocument(row.document_id);
      const filename = row.filename || documentItem?.filename || "Result";
      const category = row.category || documentItem?.category || "Uncategorized";
      const snippet = row.snippet || row.answer || "";
      return `
        <article class="result-row search-result-row">
          <div class="result-row-main">
            <span class="row-title">${escapeHtml(filename)}</span>
            <span class="row-meta">${escapeHtml(category)} - score ${escapeHtml(formatScore(row.score))}</span>
          </div>
          <p>${escapeHtml(snippet)}</p>
          <div class="result-row-actions">
            <span class="chip">${escapeHtml(documentItem?.file_type?.toUpperCase() || "DOC")}</span>
            ${row.document_id ? `<button class="button subtle" type="button" data-open-document="${row.document_id}">Open source</button>` : ""}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderResults(container, rows, emptyMessage) {
  if (container === elements.searchResults) {
    state.lastSearchRows = rows || [];
    renderSearchResults(state.lastSearchRows, emptyMessage);
    return;
  }

  if (!rows.length) {
    container.className = "result-list empty-state";
    container.textContent = emptyMessage;
    return;
  }
  container.className = "result-list";
  container.innerHTML = rows
    .map(
      (row) => `
        <article class="result-row">
          <span class="row-title">${escapeHtml(row.filename || "Result")}</span>
          <span>${escapeHtml(row.snippet || row.answer || "")}</span>
          <span class="row-meta">Document ${row.document_id || ""}${row.score ? ` - score ${row.score}` : ""}</span>
          <button class="button subtle" type="button" data-open-document="${row.document_id}">Open source</button>
        </article>
      `
    )
    .join("");
}

function renderChatCitations(citations = []) {
  const citationRows = Array.isArray(citations) ? citations : [];
  elements.chatCitationPanel.classList.toggle("has-citations", citationRows.length > 0);
  elements.chatCitations.innerHTML = citationRows.length
    ? citationRows
        .map(
          (item) => `
            <span class="citation">
              ${escapeHtml(item.filename || "Source")} - chunk ${escapeHtml(item.chunk_index ?? "n/a")}
            </span>
          `
        )
        .join("")
    : '<span class="row-meta">No citations returned.</span>';
}

function clearChatThread() {
  state.lastChatAnswer = "";
  elements.chatAnswer.classList.add("hidden");
  elements.chatAnswer.textContent = "";
  elements.chatThread.innerHTML = '<article class="assistant-message">Ask a question to see a grounded answer with citations.</article>';
  elements.chatScopeNote.textContent = "No question asked yet.";
  renderChatCitations([]);
}

function renderChatAnswer(question, payload) {
  const citations = payload.citations || [];
  const answer = payload.answer || "No answer returned.";
  const styleLabel = currentSelectLabel(elements.chatMode) || "Direct answer";
  state.lastChatAnswer = answer;
  elements.chatAnswer.classList.add("hidden");
  elements.chatAnswer.textContent = answer;
  elements.chatThread.innerHTML = `
    <article class="user-message">
      <span class="message-label">Question</span>
      ${escapeHtml(question)}
    </article>
    <article class="assistant-message">
      <span class="message-label">${escapeHtml(styleLabel)}</span>
      ${escapeHtml(answer)}
    </article>
  `;
  renderChatCitations(citations);
  elements.chatScopeNote.textContent = citations.length
    ? `${citations.length} cited source${citations.length === 1 ? "" : "s"}`
    : "No cited source was found for this answer.";
}

function renderSummaryInsights(payload) {
  const keyPoints = payload.key_points || [];
  const keyPointCount = keyPoints.length;
  const formatLabel = currentSelectLabel(elements.summaryFormat) || "Executive brief";
  elements.summaryInsights.innerHTML = `
    <div><dt>Document</dt><dd>${escapeHtml(payload.filename || "Document")}</dd></div>
    <div><dt>Key points</dt><dd>${keyPointCount}</dd></div>
    <div><dt>Format</dt><dd>${escapeHtml(formatLabel)}</dd></div>
  `;
}

function renderSummaryOutline(payload) {
  const keyPoints = payload.key_points || [];
  const firstPoint = keyPoints[0] || "Review the generated summary before sharing.";
  const followUp = keyPoints.slice(1, 4).join(" ");
  elements.summaryOutline.innerHTML = `
    <div class="outline-block">
      <span class="outline-index">1</span>
      <div>
        <strong>Overview</strong>
        <p>${escapeHtml(payload.short_summary || "No summary available.")}</p>
      </div>
    </div>
    <div class="outline-block">
      <span class="outline-index">2</span>
      <div>
        <strong>Primary finding</strong>
        <p>${escapeHtml(firstPoint)}</p>
      </div>
    </div>
    <div class="outline-block">
      <span class="outline-index">3</span>
      <div>
        <strong>Follow-up focus</strong>
        <p>${escapeHtml(followUp || "No additional follow-up points were extracted.")}</p>
      </div>
    </div>
  `;
}

function renderSummary(payload) {
  const keyPoints = payload.key_points || [];
  const formatLabel = currentSelectLabel(elements.summaryFormat) || "Executive brief";
  const summary = payload.short_summary || "No summary available.";
  elements.summaryOutput.textContent = summary;
  elements.summaryKeypoints.innerHTML = keyPoints
    .map((point) => `<li>${escapeHtml(point)}</li>`)
    .join("");
  elements.summaryStatusNote.textContent = `${formatLabel} generated for ${payload.filename || "document"}.`;
  state.lastSummaryText = [
    `${formatLabel}: ${payload.filename || "Document"}`,
    "",
    summary,
    "",
    ...keyPoints.map((point, index) => `${index + 1}. ${point}`),
  ].join("\n");
  renderSummaryInsights(payload);
  renderSummaryOutline(payload);
}

async function runSearch(query) {
  const payload = await apiRequest("/search", {
    method: "POST",
    body: {
      query,
      limit: Number(document.getElementById("search-limit").value || 5),
    },
  });
  state.lastSearchRows = payload.results || [];
  renderSearchResults(state.lastSearchRows, "No matching documents found.");
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

document.querySelectorAll(".work-tab").forEach((button) => {
  button.addEventListener("click", () => activateWorkTab(button.dataset.workTab));
});

document.querySelectorAll(".inspector-tab").forEach((button) => {
  button.addEventListener("click", () => activateInspectorTab(button.dataset.inspectorTab));
});

document.querySelectorAll(".auth-tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((tab) => tab.classList.remove("active"));
    button.classList.add("active");
    document.getElementById("login-form").classList.toggle("hidden", button.dataset.authTab !== "login");
    document.getElementById("register-form").classList.toggle("hidden", button.dataset.authTab !== "register");
  });
});

elements.accountButton.addEventListener("click", () => openAuthDialog("login"));
elements.authClose.addEventListener("click", closeAuthDialog);
elements.authDialog.addEventListener("click", (event) => {
  if (event.target === elements.authDialog) {
    closeAuthDialog();
  }
});

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("login-email").value;
  try {
    const payload = await apiRequest("/login", {
      method: "POST",
      body: {
        email,
        password: document.getElementById("login-password").value,
      },
    });
    setToken(payload.access_token, email);
    await loadDocuments();
    closeAuthDialog();
    showToast("Logged in.");
  } catch (error) {
    showToast(error.message);
  }
});

document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await apiRequest("/register", {
      method: "POST",
      body: {
        name: document.getElementById("register-name").value,
        email: document.getElementById("register-email").value,
        password: document.getElementById("register-password").value,
      },
    });
    showToast("Account created. You can log in now.");
    document.querySelector('[data-auth-tab="login"]').click();
  } catch (error) {
    showToast(error.message);
  }
});

document.getElementById("logout-button").addEventListener("click", () => {
  setToken("");
  state.documents = [];
  state.selectedDocumentId = null;
  state.selectedDetail = null;
  renderDocuments();
  renderEmptyInspector();
  showToast("Logged out.");
});

function setSelectedFiles(files) {
  state.selectedFiles = Array.from(files || []);
  renderSelectedFiles();
}

function renderSelectedFiles() {
  const count = state.selectedFiles.length;
  elements.uploadFileName.textContent = count
    ? `${count} file${count === 1 ? "" : "s"} selected`
    : "Select one or more files";
  elements.selectedFilesList.innerHTML = count
    ? state.selectedFiles
        .map((file) => `<li>${escapeHtml(file.name)} <span>${Math.ceil(file.size / 1024)} KB</span></li>`)
        .join("")
    : '<li class="muted">No files queued.</li>';
}

async function uploadSelectedFiles() {
  if (!state.selectedFiles.length) return;

  let uploadedCount = 0;
  const failedFiles = [];

  for (const file of state.selectedFiles) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiRequest("/upload", { method: "POST", formData });
      uploadedCount += 1;
    } catch (error) {
      failedFiles.push(`${file.name}: ${error.message}`);
    }
  }

  elements.uploadFile.value = "";
  state.selectedFiles = [];
  renderSelectedFiles();
  await loadDocuments();

  if (failedFiles.length) {
    throw new Error(`${uploadedCount} uploaded. ${failedFiles.join(" | ")}`);
  }
}

elements.uploadFile.addEventListener("change", () => {
  setSelectedFiles(elements.uploadFile.files);
});

["dragenter", "dragover"].forEach((eventName) => {
  elements.uploadDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.uploadDropzone.classList.add("drag-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  elements.uploadDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.uploadDropzone.classList.remove("drag-over");
  });
});

elements.uploadDropzone.addEventListener("drop", (event) => {
  const files = Array.from(event.dataTransfer.files || []);
  if (!files.length) return;
  const dataTransfer = new DataTransfer();
  files.forEach((file) => dataTransfer.items.add(file));
  elements.uploadFile.files = dataTransfer.files;
  setSelectedFiles(dataTransfer.files);
});

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedFiles.length) return;

  try {
    const count = state.selectedFiles.length;
    setBusy(true, count === 1 ? "Extracting" : `Extracting ${count}`);
    elements.extractionHealth.textContent = "Extracting";
    await uploadSelectedFiles();
    showToast(`${count} file${count === 1 ? "" : "s"} uploaded, extracted, and indexed.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
    renderExtractionHealth();
  }
});

document.getElementById("refresh-documents").addEventListener("click", async () => {
  try {
    await loadDocuments();
    showToast("Documents refreshed.");
  } catch (error) {
    showToast(error.message);
  }
});

elements.documentFilter.addEventListener("input", () => {
  state.documentFilter = elements.documentFilter.value;
  renderDocumentTable();
});

elements.categoryFilter.addEventListener("change", () => {
  state.categoryFilter = elements.categoryFilter.value;
  renderDocumentTable();
});

[elements.searchDocument, elements.searchCategoryFilter, elements.searchSort].forEach((control) => {
  control.addEventListener("change", () => renderSearchResults());
});

document.addEventListener("click", async (event) => {
  const openButton = event.target.closest("[data-open-document]");
  if (!openButton) return;

  try {
    await openDocument(Number(openButton.dataset.openDocument));
  } catch (error) {
    showToast(error.message);
  }
});

elements.deleteDocument.addEventListener("click", async () => {
  if (!state.selectedDocumentId) return;
  try {
    await apiRequest(`/document/${state.selectedDocumentId}`, { method: "DELETE" });
    const deletedName = state.selectedDetail?.filename || "Document";
    state.selectedDocumentId = null;
    state.selectedDetail = null;
    renderEmptyInspector();
    await loadDocuments();
    showToast("Document deleted.");
  } catch (error) {
    showToast(error.message);
  }
});

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    setBusy(true, "Working");
    await runSearch(document.getElementById("search-query").value);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

document.getElementById("global-search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("global-query").value.trim();
  if (!query) return;
  document.getElementById("search-query").value = query;
  activateView("dashboard");
  activateWorkTab("search");
  try {
    setBusy(true, "Working");
    await runSearch(query);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

document.getElementById("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    setBusy(true, "Thinking");
    const documentId = document.getElementById("chat-document").value;
    const question = document.getElementById("chat-question").value;
    const payload = await apiRequest("/chat", {
      method: "POST",
      body: {
        question,
        document_id: documentId ? Number(documentId) : null,
      },
    });
    renderChatAnswer(question, payload);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

document.getElementById("chat-clear").addEventListener("click", clearChatThread);

elements.chatCopy.addEventListener("click", () => {
  copyTextToClipboard(state.lastChatAnswer, "Answer copied.");
});

document.getElementById("summary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    setBusy(true, "Summarizing");
    const payload = await apiRequest("/summarize", {
      method: "POST",
      body: {
        document_id: Number(document.getElementById("summary-document").value),
        max_key_points: Number(document.getElementById("summary-points").value),
      },
    });
    renderSummary(payload);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

elements.summaryCopy.addEventListener("click", () => {
  copyTextToClipboard(state.lastSummaryText, "Summary copied.");
});

elements.summaryFormat.addEventListener("change", () => {
  const defaults = {
    executive: 3,
    detailed: 8,
    actions: 5,
  };
  document.getElementById("summary-points").value = defaults[elements.summaryFormat.value] || 5;
  elements.summaryStatusNote.textContent = `${currentSelectLabel(elements.summaryFormat)} selected.`;
});

document.querySelectorAll("[data-search-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById("search-query").value = button.dataset.searchPreset;
    activateWorkTab("search");
  });
});

document.querySelectorAll("[data-chat-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById("chat-question").value = button.dataset.chatPrompt;
    activateWorkTab("chat");
  });
});

document.querySelectorAll("[data-summary-points]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById("summary-points").value = button.dataset.summaryPoints;
  });
});

renderAuthState();
renderSelectedFiles();
renderEmptyInspector();
loadDocuments().catch((error) => {
  showToast(error.message);
});
