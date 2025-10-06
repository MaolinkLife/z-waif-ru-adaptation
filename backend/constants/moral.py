# Default emotional state values
DEFAULT_EMOTIONAL_STATE = {
    "joy": 0.5,
    "sadness": 0.2,
    "anger": 0.1,
    "fear": 0.1,
    "surprise": 0.3,
    "disgust": 0.05,
}

DEFAULT_RELATIONSHIP_SCORE = 0.7  # scale 0-1

# Mapping emotions to human-readable text
EMOTION_MAP = {
    "joy": "joy",
    "sadness": "sadness",
    "anger": "anger",
    "fear": "fear",
    "surprise": "surprise",
    "disgust": "disgust",
}

# Relationship status thresholds
RELATIONSHIP_STATUSES = [
    (0.8, "very close"),
    (0.6, "friendly"),
    (0.4, "neutral"),
    (0.0, "formal"),
]

# Behavioral recommendations for each dominant emotion
BEHAVIORAL_RECOMMENDATIONS = {
    "joy": ["be playful", "maintain positive tone"],
    "sadness": ["offer support", "be empathetic"],
    "anger": ["be patient", "avoid confrontation"],
    "fear": ["be calming", "provide reassurance"],
    "surprise": ["be curious", "encourage interest"],
    "disgust": ["be delicate", "avoid arguments"],
}

FALLBACK_RECOMMENDATION = ["be natural"]
