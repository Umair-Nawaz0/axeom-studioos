import hashlib
from typing import Any, Dict, List, Optional

from ..config import settings

JEV_CATEGORIES = [
    "Privacy / No-Release Alert",
    "Complaint / Revision Follow-up",
    "Contract & Retention Risk",
    "Video Revision Request",
    "Sales / Upsell / Referral",
    "Billing & Payment",
    "Shoot Logistics & Scheduling",
    "Contact / Brand Update",
    "Client Praise & Approval",
    "Spam / Phishing",
    "Studio Announcement",
]

_CLASSIFICATION_CACHE: Dict[str, Dict[str, Any]] = {}


def heuristic_classifier(text: str) -> Dict[str, Any]:
    """
    Deterministic rule-based classifier used while external Jev API integration is deferred.
    """
    b = (text or "").lower()
    if any(k in b for k in ("quick tip from", "send edit notes as a voice note", "studio announcement")):
        return {
            "category": "Studio Announcement",
            "confidence": 0.99,
            "is_urgent_prob": 0.05,
            "has_privacy_risk_prob": 0.01,
        }
    if any(
        k in b
        for k in ("verify here:", "partnership offer:", "final notice:", "real followers", "invoice.zip", "bit.ly/")
    ):
        return {
            "category": "Spam / Phishing",
            "confidence": 0.97,
            "is_urgent_prob": 0.02,
            "has_privacy_risk_prob": 0.01,
        }
    if any(k in b for k in ("blur the face", "didn't sign the release", "did not sign the release", "no release")):
        return {
            "category": "Privacy / No-Release Alert",
            "confidence": 0.98,
            "is_urgent_prob": 0.99,
            "has_privacy_risk_prob": 0.99,
        }
    if any(
        k in b
        for k in (
            "pause after this month",
            "talk about our contract",
            "whether we continue",
            "talk about the contract",
            "compliance cares about this",
        )
    ):
        return {
            "category": "Contract & Retention Risk",
            "confidence": 0.95,
            "is_urgent_prob": 0.96,
            "has_privacy_risk_prob": 0.05,
        }
    if any(
        k in b
        for k in (
            "second time i ask",
            "not fixed",
            "still wrong",
            "frustrated",
            "same problem",
            "asked for the full name",
            "not happy",
        )
    ):
        return {
            "category": "Complaint / Revision Follow-up",
            "confidence": 0.94,
            "is_urgent_prob": 0.92,
            "has_privacy_risk_prob": 0.05,
        }
    if any(
        k in b
        for k in (
            "how much",
            "booking link",
            "package where you cut short clips",
            "cut short clips from our episodes",
            "do this every month",
            "what would that cost",
            "wants videos too",
            "loved our reels",
            "needs videos",
            "call him",
        )
    ):
        return {
            "category": "Sales / Upsell / Referral",
            "confidence": 0.93,
            "is_urgent_prob": 0.78,
            "has_privacy_risk_prob": 0.01,
        }
    if any(k in b for k in ("office number is", "new email is", "use this one from now on", "big news:")):
        return {
            "category": "Contact / Brand Update",
            "confidence": 0.95,
            "is_urgent_prob": 0.60,
            "has_privacy_risk_prob": 0.01,
        }
    if any(
        k in b
        for k in (
            "please bill us",
            "cash is tight",
            "sessions together",
            "sent half",
            "15% off studio sessions",
            "already paid",
            "accounting will handle the invoice",
            "pay once the videos are posted",
        )
    ):
        return {
            "category": "Billing & Payment",
            "confidence": 0.93,
            "is_urgent_prob": 0.75,
            "has_privacy_risk_prob": 0.01,
        }
    if any(k in b for k in ("parking", "move to 2pm", "see you tomorrow", "bring anything", "running 10 min late")):
        return {
            "category": "Shoot Logistics & Scheduling",
            "confidence": 0.91,
            "is_urgent_prob": 0.35,
            "has_privacy_risk_prob": 0.01,
        }
    if any(
        k in b
        for k in (
            "approved! post it",
            "sales went up",
            "thanks team",
            "three new cases",
            "best content team",
            "love it",
        )
    ):
        return {
            "category": "Client Praise & Approval",
            "confidence": 0.94,
            "is_urgent_prob": 0.15,
            "has_privacy_risk_prob": 0.01,
        }
    if any(
        k in b
        for k in (
            "caption",
            "spelled wrong",
            "too loud",
            "calmer song",
            "brand color",
            "stumble",
            "cut the first",
            "add our phone number",
            "prices are changing",
            "walk-ins welcome",
            "use the other shot",
            "changed our mind",
        )
    ):
        return {
            "category": "Video Revision Request",
            "confidence": 0.92,
            "is_urgent_prob": 0.65,
            "has_privacy_risk_prob": 0.02,
        }
    return {
        "category": "Video Revision Request",
        "confidence": 0.70,
        "is_urgent_prob": 0.40,
        "has_privacy_risk_prob": 0.02,
    }


def build_typesafe_systemone_payload(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Modular integration payload builder reserved for future TypeSafe Jev System One API activation
    once an API key is provided.
    """
    return {
        "model": model or settings.TYPESAFE_MODEL or "jev-latest",
        "state": text,
        "questions": [
            {
                "type": "choice",
                "id": "intent_category",
                "prompt": "Classify the primary studio operational intent of this message.",
                "options": JEV_CATEGORIES,
            },
            {
                "type": "noul",
                "id": "is_urgent",
                "prompt": "Does this message require urgent studio owner or editor action today?",
            },
            {
                "type": "noul",
                "id": "has_privacy_risk",
                "prompt": "Does this message report an unsigned release or request blurring a client's face?",
            },
        ],
    }


def classify_message(text: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Deterministic local message classification.
    External Jev API calls are deferred until a valid API key is configured.
    """
    cache_key = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    if use_cache and cache_key in _CLASSIFICATION_CACHE:
        cached_resp = dict(_CLASSIFICATION_CACHE[cache_key])
        cached_resp["cached"] = True
        return cached_resp

    fallback = heuristic_classifier(text)
    result = {
        "text": text,
        "category": fallback["category"],
        "confidence": fallback["confidence"],
        "provider": "deterministic_rules",
        "model": "local-deterministic-rules",
        "cached": False,
        "is_urgent_prob": fallback["is_urgent_prob"],
        "has_privacy_risk_prob": fallback["has_privacy_risk_prob"],
        "notes": "Classified via deterministic local rules (Jev API integration deferred — no API key configured).",
    }
    if use_cache:
        _CLASSIFICATION_CACHE[cache_key] = result
    return result


def evaluate_jev_benchmark() -> Dict[str, Any]:
    """
    Returns transparent status that external Jev evaluation is deferred because no API key is configured.
    """
    api_key_configured = bool(settings.TYPESAFE_API_KEY or settings.JEV_API_KEY)
    return {
        "status": "deferred_no_api_key" if not api_key_configured else "ready_for_key_activation",
        "task_name": "Inbound Message Intent, Privacy Release & Churn Triage",
        "api_key_configured": api_key_configured,
        "active_provider": "deterministic_rules",
        "sample_size": 0,
        "correct_predictions": 0,
        "accuracy_percentage": None,
        "evaluation_summary": (
            "External Jev API evaluation is deferred because no Jev API key has been provided. "
            "All message classification, request tracking, lead parsing, and risk flags currently run "
            "via deterministic rule-based logic."
        ),
        "per_label_metrics": [],
        "confusion_matrix": {},
        "misclassified_samples": [],
        "samples": [],
    }
