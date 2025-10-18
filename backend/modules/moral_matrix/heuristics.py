"""Lightweight emotion/intent heuristics used by MoralMatrix as a fallback."""

from __future__ import annotations

import re
from typing import Dict, List

from services.logger_service import AuditStatus, log_audit_entry

# RU Segment
INTENT_PATTERNS_RU = {
    "признание": r"(люблю|нравишься|дорога|значишь|ценю)",
    "угроза": r"(убью|разнесу|уничтожу|поквитаюсь)",
    "вопрос": r"(ты\s+знаешь|можешь|почему|зачем|что если)",
    "обида": r"(всегда так|опять|ты даже не|как всегда|обидно)",
    "забота": r"(волнуешься|тебе важно|позаботиться|будь осторожна)",
}

EMOTION_KEYWORDS_RU = {
    "sadness": ["печально", "жаль", "одиноко", "слёзы", "не хватает", "тоска"],
    "joy": ["счастлив", "рад", "ура", "восторг", "приятно", "улыбка"],
    "anger": ["ненавижу", "раздражает", "бесит", "злой", "убил бы", "ярость"],
    "love": ["дорога", "люблю", "нравишься", "значишь", "ценю", "не безразлична"],
    "fear": ["боюсь", "страшно", "тревожно", "опасаюсь", "паника", "дрожь"],
}

# EN Segment
INTENT_PATTERNS_EN = {
    "confession": r"(I love you|like you|dear you|mean you|I appreciate you)",
    "threat": r"(I'll kill you|I'll smash you|I'll destroy you|I'll get even)",
    "question": r"(you\s+know|you can|why|what for|what if)",
    "offense": r"(always like this|again|you don't even|like always|offensive)",
    "care": r"(you're worried|it's important to you|to take care|be careful)",
}

EMOTION_KEYWORDS_EN = {
    "sadness": ["sad", "pity", "lonely", "tears", "miss", "longing"],
    "joy": ["happy", "glad", "hooray", "delight", "pleased", "smile"],
    "anger": ["hate", "annoying", "infuriating", "angry", "would kill", "rage"],
    "love": ["road", "love", "like you", "mean", "appreciate", "care about you"],
    "fear": ["afraid", "scared", "anxious", "fearful", "panic", "trembling"],
}

POLARITY_MAP = {
    "sadness": "negative",
    "joy": "positive",
    "anger": "negative",
    "love": "positive",
    "fear": "negative",
}


def analyze_emotion(text: str) -> Dict[str, any]:
    text_lower = (text or "").lower()
    detected_emotions: List[str] = []

    for emotion, keywords in EMOTION_KEYWORDS_RU.items():
        if any(kw in text_lower for kw in keywords):
            detected_emotions.append(emotion)

    for emotion, keywords in EMOTION_KEYWORDS_EN.items():
        if any(kw in text_lower for kw in keywords):
            detected_emotions.append(emotion)

    tone = "neutral"
    if "love" in detected_emotions and "sadness" in detected_emotions:
        tone = "sadness with a warm undertone"
    elif "sadness" in detected_emotions:
        tone = "sad"
    elif "joy" in detected_emotions:
        tone = "glad"
    elif "anger" in detected_emotions:
        tone = "irritated"
    elif "love" in detected_emotions:
        tone = "warm"
    elif "fear" in detected_emotions:
        tone = "anxious"

    intent = "undefined"
    for label, pattern in INTENT_PATTERNS_RU.items():
        if re.search(pattern, text_lower):
            intent = label
            break

    if intent == "undefined":
        for label, pattern in INTENT_PATTERNS_EN.items():
            if re.search(pattern, text_lower):
                intent = label
                break

    polarity_scores = [POLARITY_MAP.get(e, "neutral") for e in detected_emotions]
    dominant_polarity = "neutral"
    if polarity_scores:
        pos = polarity_scores.count("positive")
        neg = polarity_scores.count("negative")
        if pos > neg:
            dominant_polarity = "positive"
        elif neg > pos:
            dominant_polarity = "negative"

    analysis = {
        "tone": tone,
        "intent": intent,
        "confidence": round(min(1.0, len(detected_emotions) * 0.25), 2),
        "meta": {
            "detected_emotions": detected_emotions,
            "dominant_emotions": detected_emotions[:2],
            "secondary_emotions": detected_emotions[2:],
            "polarity": dominant_polarity,
        },
    }

    log_audit_entry(
        "moral_matrix_heuristics_run",
        "[MoralMatrix/Heuristics] Emotion heuristics executed.",
        AuditStatus.INFO,
        details={
            "tone": tone,
            "intent": intent,
            "detected_emotions": detected_emotions,
            "polarity": dominant_polarity,
        },
    )

    return analysis


def generate_instruction(analysis: Dict[str, any]) -> str:
    tone = analysis["tone"]
    polarity = analysis["meta"]["polarity"]
    primary = ", ".join(analysis["meta"]["dominant_emotions"])
    secondary = ", ".join(analysis["meta"]["secondary_emotions"])

    description = f"You feel {primary or 'neutral'} ({polarity} emotions)"
    if secondary:
        description += f", also present {secondary}."
    description += f" Answer in tone: {tone}."

    log_audit_entry(
        "moral_matrix_heuristics_instruction",
        "[MoralMatrix/Heuristics] Generated fallback instruction.",
        AuditStatus.INFO,
        details={"instruction": description},
    )

    return description

