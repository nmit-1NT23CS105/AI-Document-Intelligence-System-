# AI Document Intelligence System

A FastAPI document workspace for PDF and DOCX upload, text extraction, metadata, semantic search, grounded chat, summaries, and a static web dashboard.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Features

- Register and login with JWT authentication.
- Upload PDF or DOCX documents.
- Extract readable text, reject empty/scanned PDFs when OCR is unavailable, and remove common scanner watermark artifacts.
- Classify documents into categories such as Invoice, Contract, Policy, Report, Resume, Research Paper, Manual, or Other.
- Chunk and index extracted text for local semantic search.
- Chat over uploaded content with citations, with optional Gemini-powered RAG answers.
- Generate short summaries and key points, with optional Gemini-powered summaries.
- Use the advanced dashboard for upload state, filters, preview, metadata, search, chat, and summary workflows.

## Optional Gemini LLM

The app works without an LLM by using local retrieval, sentence matching, and extractive summaries. To enable Google Gemini for generated chat answers and summaries, create a local `.env` file from `.env.example` and set:

```env
LLM_PROVIDER="gemini"
GEMINI_API_KEY="your-google-ai-studio-key"
GEMINI_MODEL="gemini-3.5-flash"
```

Keep real API keys in `.env` only. Do not commit them to GitHub.

## OCR Note

Text-based PDFs and DOCX files work out of the box. Scanned/image-only PDFs require a local Tesseract OCR installation that PyMuPDF can use. If OCR is not available, the API returns a clear upload error instead of indexing an empty document.

## Test

```powershell
.\.venv\Scripts\python -m pytest
```

## Docker

```powershell
docker build -t ai-document-intelligence .
docker run --rm -p 8000:8000 ai-document-intelligence
```
