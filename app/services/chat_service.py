from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.ai.llm import get_llm_client
from app.database.models import ChatHistory, User
from app.schemas.chat import ChatCitation
from app.services.document_service import get_user_document
from app.services.search_service import SearchMatch, search_documents

NO_ANSWER = "I could not find an answer in the uploaded documents."
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SENTENCE_PATTERN = re.compile(r"[^.!?\n]+[.!?]?")
QUESTION_STOP_WORDS = {
    "a",
    "an",
    "are",
    "available",
    "can",
    "do",
    "does",
    "from",
    "how",
    "in",
    "is",
    "many",
    "much",
    "of",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in QUESTION_STOP_WORDS
    }


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in SENTENCE_PATTERN.findall(text) if sentence.strip()]


def _answer_candidates(sentence: str) -> list[str]:
    words = sentence.split()
    candidates = [sentence]
    for index in range(1, min(8, len(words) - 3) + 1):
        prefix = words[:index]
        if not all(word[:1].isupper() for word in prefix if word[:1].isalpha()):
            continue
        candidates.append(" ".join(words[index:]))
    return candidates


def _best_answer_sentence(question: str, matches: list[SearchMatch]) -> tuple[str, SearchMatch | None]:
    question_tokens = _tokens(question)
    best_sentence = ""
    best_match: SearchMatch | None = None
    best_score = 0

    for match in matches:
        for sentence in _sentences(match.snippet):
            for candidate in _answer_candidates(sentence):
                overlap = len(question_tokens.intersection(_tokens(candidate)))
                if overlap > best_score or (
                    overlap == best_score
                    and overlap > 0
                    and (not best_sentence or len(candidate) < len(best_sentence))
                ):
                    best_score = overlap
                    best_sentence = candidate
                    best_match = match

    minimum_overlap = 2 if len(question_tokens) >= 2 else 1
    if best_score < minimum_overlap:
        return NO_ANSWER, None

    return best_sentence, best_match


def _citations_from_matches(matches: list[SearchMatch]) -> list[ChatCitation]:
    citations: list[ChatCitation] = []
    seen: set[tuple[int, int]] = set()

    for match in matches:
        key = (match.document_id, match.chunk_index)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            ChatCitation(
                document_id=match.document_id,
                filename=match.filename,
                chunk_index=match.chunk_index,
            )
        )

    return citations


def _format_chat_context(matches: list[SearchMatch]) -> str:
    return "\n\n".join(
        (
            f"[Source {index}: {match.filename}, chunk {match.chunk_index}, "
            f"score {match.score}]\n{match.snippet}"
        )
        for index, match in enumerate(matches, start=1)
    )


def _llm_answer_question(question: str, matches: list[SearchMatch]) -> tuple[str, list[ChatCitation]] | None:
    llm_client = get_llm_client()
    if llm_client is None or not matches:
        return None

    system_prompt = (
        "You answer questions using only the provided document context. "
        "If the context does not contain the answer, say exactly: "
        f"{NO_ANSWER} Keep answers concise and do not invent facts."
    )
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Document context:\n{_format_chat_context(matches)}\n\n"
        "Answer using the document context only."
    )

    try:
        answer = llm_client.generate_text(system_prompt, user_prompt).strip()
    except Exception:
        return None

    if not answer:
        return None
    if answer == NO_ANSWER:
        return answer, []
    return answer, _citations_from_matches(matches)


def answer_question(
    db: Session,
    user: User,
    question: str,
    document_id: int | None,
    limit: int,
) -> tuple[str, list[ChatCitation]]:
    if document_id is not None:
        get_user_document(db=db, user=user, document_id=document_id)

    matches = search_documents(
        db=db,
        user=user,
        query=question,
        limit=limit,
        document_id=document_id,
    )

    llm_result = _llm_answer_question(question=question, matches=matches)
    if llm_result is not None:
        answer, citations = llm_result
    else:
        answer, match = _best_answer_sentence(question=question, matches=matches)
        citations = []
        if match is not None:
            citations.append(
                ChatCitation(
                    document_id=match.document_id,
                    filename=match.filename,
                    chunk_index=match.chunk_index,
                )
            )

    history_document_id = citations[0].document_id if citations else document_id
    if history_document_id is not None:
        db.add(
            ChatHistory(
                user_id=user.id,
                document_id=history_document_id,
                question=question,
                answer=answer,
            )
        )
        db.commit()

    return answer, citations
