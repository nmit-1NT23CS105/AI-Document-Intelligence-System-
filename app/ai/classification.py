from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings

CATEGORIES = [
    "Resume",
    "Invoice",
    "Contract",
    "Policy",
    "Report",
    "Research Paper",
    "Manual",
    "Other",
]

TRAINING_EXAMPLES = [
    ("skills experience education projects resume curriculum vitae", "Resume"),
    ("invoice bill payment amount due total subtotal tax", "Invoice"),
    ("agreement contract party terms obligations signature renewal", "Contract"),
    ("policy leave benefits employees rules approval compliance", "Policy"),
    ("report quarterly performance revenue findings analysis metrics", "Report"),
    ("abstract methodology references research experiment paper literature", "Research Paper"),
    ("manual instructions setup troubleshooting user guide installation", "Manual"),
    ("general document notes miscellaneous information", "Other"),
]

KEYWORD_HINTS = {
    "Resume": {"resume", "curriculum", "vitae", "skills", "experience", "education"},
    "Invoice": {"invoice", "bill", "payment", "amount", "due", "subtotal", "total"},
    "Contract": {"contract", "agreement", "party", "obligations", "signature", "renewal"},
    "Policy": {"policy", "leave", "employees", "rules", "approval", "benefits"},
    "Report": {"report", "quarterly", "performance", "revenue", "findings", "metrics"},
    "Research Paper": {"abstract", "methodology", "references", "literature", "experiment"},
    "Manual": {"manual", "instructions", "setup", "troubleshooting", "guide", "installation"},
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class DocumentClassifier(Protocol):
    def classify(self, text: str) -> str:
        ...


class KeywordDocumentClassifier:
    def classify(self, text: str) -> str:
        tokens = set(TOKEN_PATTERN.findall(text.lower()))
        best_category = "Other"
        best_score = 0

        for category, keywords in KEYWORD_HINTS.items():
            score = len(tokens.intersection(keywords))
            if score > best_score:
                best_category = category
                best_score = score

        return best_category


class SklearnDocumentClassifier:
    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        texts = [example[0] for example in TRAINING_EXAMPLES]
        labels = [example[1] for example in TRAINING_EXAMPLES]
        self.pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer()),
                ("classifier", LogisticRegression(max_iter=1000)),
            ]
        )
        self.pipeline.fit(texts, labels)

    def classify(self, text: str) -> str:
        prediction = self.pipeline.predict([text or ""])[0]
        return str(prediction)


@lru_cache
def get_document_classifier() -> DocumentClassifier:
    settings = get_settings()
    if settings.classifier_provider == "scikit-learn":
        try:
            return SklearnDocumentClassifier()
        except ImportError:
            return KeywordDocumentClassifier()
    return KeywordDocumentClassifier()
