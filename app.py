import os
import json
import uuid
import re
import statistics
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from groq import Groq
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# ============================================================
# SETUP
# ============================================================

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

LOG_FILE = "audit_log.json"

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)


# ============================================================
# SIGNAL 1: LLM-BASED DETECTION
# ============================================================

def llm_detection(text):
    prompt = f"""
You are analyzing text for possible AI-generated writing.

Estimate how likely the following text is to be AI-generated.

Return ONLY valid JSON in this exact format:
{{"ai_score": 0.0}}

The ai_score must be a number between 0.0 and 1.0.

0.0 means strongly human-written.
1.0 means strongly AI-generated.

Consider writing style, structure, consistency, phrasing,
and patterns that may indicate AI-generated writing.

Text:
{text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    result = json.loads(response.choices[0].message.content)

    ai_score = float(result["ai_score"])

    return max(0.0, min(1.0, ai_score))


# ============================================================
# SIGNAL 2: STYLOMETRIC HEURISTICS
# ============================================================

def stylometric_detection(text):
    """
    Analyze measurable structural characteristics of the text.

    Metrics:
    1. Sentence-length variation
    2. Vocabulary diversity
    3. Punctuation density

    Returns an AI-likelihood score between 0.0 and 1.0.
    """

    words = re.findall(r"\b[\w'-]+\b", text.lower())

    sentences = [
        sentence.strip()
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]

    if not words or not sentences:
        return 0.5

    # --------------------------------
    # Metric 1: Sentence length variance
    # --------------------------------

    sentence_lengths = [
        len(re.findall(r"\b[\w'-]+\b", sentence))
        for sentence in sentences
    ]

    if len(sentence_lengths) > 1:
        sentence_variance = statistics.pvariance(sentence_lengths)
    else:
        sentence_variance = 0

    # Uniform sentence lengths are treated as more AI-like.
    if sentence_variance < 5:
        variance_score = 0.80
    elif sentence_variance < 15:
        variance_score = 0.65
    elif sentence_variance < 30:
        variance_score = 0.50
    else:
        variance_score = 0.30

    # --------------------------------
    # Metric 2: Vocabulary diversity
    # --------------------------------

    unique_words = len(set(words))
    type_token_ratio = unique_words / len(words)

    if type_token_ratio < 0.45:
        vocabulary_score = 0.75
    elif type_token_ratio < 0.60:
        vocabulary_score = 0.60
    elif type_token_ratio < 0.75:
        vocabulary_score = 0.45
    else:
        vocabulary_score = 0.30

    # --------------------------------
    # Metric 3: Punctuation density
    # --------------------------------

    punctuation_count = len(re.findall(r"[,:;!?—-]", text))
    punctuation_density = punctuation_count / max(len(words), 1)

    if 0.05 <= punctuation_density <= 0.15:
        punctuation_score = 0.60
    elif punctuation_density < 0.05:
        punctuation_score = 0.50
    else:
        punctuation_score = 0.40

    # Combine the three stylometric measurements.
    stylometric_score = (
        variance_score * 0.40
        + vocabulary_score * 0.40
        + punctuation_score * 0.20
    )

    return round(max(0.0, min(1.0, stylometric_score)), 3)


# ============================================================
# CONFIDENCE SCORING
# ============================================================

def calculate_confidence(llm_score, stylometric_score):
    """
    Combine the two independent detection signals.

    LLM = 60%
    Stylometric = 40%
    """

    combined_score = (
        llm_score * 0.60
        + stylometric_score * 0.40
    )

    return round(combined_score, 3)


# ============================================================
# ATTRIBUTION
# ============================================================

def get_attribution(confidence):
    if confidence >= 0.70:
        return "likely_ai"

    if confidence <= 0.34:
        return "likely_human"

    return "uncertain"


# ============================================================
# TRANSPARENCY LABEL
# ============================================================

def generate_label(confidence):
    if confidence >= 0.70:
        return (
            "Likely AI-Generated: Our analysis found strong indicators "
            "that this content may have been generated by AI. This "
            "classification is based on multiple detection signals and "
            "is not a definitive determination of authorship."
        )

    if confidence <= 0.34:
        return (
            "Likely Human-Written: Our analysis found strong indicators "
            "that this content was written by a human. This classification "
            "is based on multiple detection signals and is not a definitive "
            "determination of authorship."
        )

    return (
        "Uncertain: Our analysis found mixed indicators and cannot "
        "confidently determine whether this content was human-written "
        "or AI-generated."
    )


# ============================================================
# AUDIT LOG
# ============================================================

def get_log():
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_log(entries):
    with open(LOG_FILE, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=4)


def add_log_entry(entry):
    entries = get_log()
    entries.append(entry)
    save_log(entries)


# ============================================================
# HOME ENDPOINT
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Provenance Guard API is running"
    })


# ============================================================
# SUBMISSION ENDPOINT
# ============================================================

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "JSON body is required"
        }), 400

    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not creator_id:
        return jsonify({
            "error": "text and creator_id are required"
        }), 400

    content_id = str(uuid.uuid4())

    try:
        # Signal 1
        llm_score = llm_detection(text)

        # Signal 2
        stylometric_score = stylometric_detection(text)

        # Combined confidence
        confidence = calculate_confidence(
            llm_score,
            stylometric_score
        )

        attribution = get_attribution(confidence)

        label = generate_label(confidence)

        log_entry = {
            "content_id": content_id,
            "creator_id": creator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attribution": attribution,
            "confidence": confidence,
            "llm_score": llm_score,
            "stylometric_score": stylometric_score,
            "status": "classified",
            "appeal_reasoning": None
        }

        add_log_entry(log_entry)

        return jsonify({
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": label,
            "signals": {
                "llm_score": llm_score,
                "stylometric_score": stylometric_score
            },
            "status": "classified"
        })

    except Exception as error:
        return jsonify({
            "error": "Unable to analyze submission",
            "details": str(error)
        }), 500


# ============================================================
# APPEAL ENDPOINT
# ============================================================

@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "JSON body is required"
        }), 400

    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({
            "error": "content_id and creator_reasoning are required"
        }), 400

    entries = get_log()

    original_entry = None

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("attribution") is not None
        ):
            original_entry = entry
            break

    if original_entry is None:
        return jsonify({
            "error": "Content ID not found"
        }), 404

    # Update original decision status.
    original_entry["status"] = "under_review"
    original_entry["appeal_reasoning"] = creator_reasoning

    # Add a separate structured appeal event.
    appeal_entry = {
        "content_id": content_id,
        "creator_id": original_entry.get("creator_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "appeal",
        "attribution": original_entry.get("attribution"),
        "confidence": original_entry.get("confidence"),
        "llm_score": original_entry.get("llm_score"),
        "stylometric_score": original_entry.get(
            "stylometric_score"
        ),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning
    }

    entries.append(appeal_entry)

    save_log(entries)

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received successfully.",
        "creator_reasoning": creator_reasoning
    })


# ============================================================
# AUDIT LOG ENDPOINT
# ============================================================

@app.route("/log", methods=["GET"])
def log():
    return jsonify({
        "entries": get_log()
    })


# ============================================================
# RATE LIMIT ERROR
# ============================================================

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Please wait before submitting more content."
    }), 429


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)