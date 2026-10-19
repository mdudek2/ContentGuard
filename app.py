import os
import csv
import json
import base64
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
import requests
from flask import Flask, render_template, request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# Configuration
THUMBNAIL_DIR = Path("./thumbnails")
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = Path("./thumbnail_moderation.csv")
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "minicpm-v4.6:latest"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = Flask(__name__)

youtube = (
    build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    if YOUTUBE_API_KEY
    else None
)

# Avoid overlapping CSV writes within this process.
csv_lock = threading.Lock()

CSV_FIELDS = [
    "timestamp",
    "video_id",
    "title",
    "model",
    "classification",
    "reason",
    "raw_response",
    "error",
]

def log_result(video_id, title, classification, reason="", raw_response="", error=""):
    """Append one moderation result to the CSV file."""
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_id": video_id,
        "title": title,
        "model": OLLAMA_MODEL,
        "classification": classification,
        "reason": reason,
        "raw_response": raw_response,
        "error": error,
    }

    with csv_lock:
        file_exists = CSV_PATH.exists()

        with CSV_PATH.open(
            "a", newline="", encoding="utf-8"
        ) as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=CSV_FIELDS
            )

            if not file_exists or CSV_PATH.stat().st_size == 0:
                writer.writeheader()

            writer.writerow(row)

def download_thumbnail(video_id, thumbnails):
    """Download a thumbnail and return its local path."""
    for size in ("maxres", "standard", "high", "medium", "default"):
        thumbnail = thumbnails.get(size)

        if not thumbnail:
            continue

        try:
            response = requests.get(
                thumbnail["url"], timeout=10
            )
            response.raise_for_status()

            # Keep the filename unique to this video.
            file_path = THUMBNAIL_DIR / f"{video_id}.jpg"
            file_path.write_bytes(response.content)

            return file_path

        except requests.RequestException:
            continue

    return None

import base64
import json
import re
import requests

def moderate_thumbnail(image_path):
    """Classify a thumbnail using Ollama with a robust regex JSON scavenger."""
    raw_response = ""

    try:
        image_base64 = base64.b64encode(
            image_path.read_bytes()
        ).decode("utf-8")

        payload = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict API microservice. Your ONLY output must be a raw JSON object "
                        "with no markdown formatting, no code blocks, and no extra text. "
                        "The JSON must look like this exact template: "
                        '{"classification": "SAFE", "reason": "short sentence here"}\n'
                        "Rules:\n"
                        "1. classification must be 'SAFE' or 'INAPPROPRIATE'.\n"
                        "2. reason must be under 15 words.\n"
                        "3. Do not include markdown ticks like ```json."
                    ),
                },
                {
                    "role": "user",
                    "content": "Classify this image now.",
                    "images": [image_base64],
                },
            ],
            "options": {
                "temperature": 0,
                "num_predict": 400,
            },
        }

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        response_data = response.json()
        raw_response = response_data.get("message", {}).get("content", "").strip()

        # --- ADVANCED JSON EXTRACTION & REPAIR ---
        result = None
        
        # Attempt 1: Direct load
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # Attempt 2: Extract content inside markdown blocks if present
        if result is None:
            code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if code_block_match:
                try:
                    result = json.loads(code_block_match.group(1))
                except json.JSONDecodeError:
                    pass

        # Attempt 3: Scavenge the raw string for the first outer curly braces { ... }
        if result is None:
            braces_match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
            if braces_match:
                try:
                    result = json.loads(braces_match.group(1))
                except json.JSONDecodeError:
                    pass

        # If all attempts failed, throw a descriptive error containing what the model actually said
        if result is None or not isinstance(result, dict):
            raise json.JSONDecodeError(
                f"Could not extract valid JSON object from model output. Raw output was: {repr(raw_response)}",
                raw_response,
                0
            )
        # ----------------------------------------

        classification = result.get("classification")
        reason = result.get("reason", "")

        if classification not in ("SAFE", "INAPPROPRIATE"):
            return (
                "ERROR",
                str(reason),
                raw_response,
                "Unknown classification",
            )

        if not isinstance(reason, str):
            return (
                "ERROR",
                "",
                raw_response,
                "Invalid reason type",
            )

        return classification, reason, raw_response, ""

    except json.JSONDecodeError as exc:
        return (
            "ERROR",
            "",
            raw_response,
            f"Invalid JSON response: {exc}",
        )

    except (
        requests.RequestException,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        return "ERROR", "", raw_response, str(exc)

@app.route("/", methods=["GET", "POST"])
def index():
    query = ""
    results = []

    if request.method == "POST":
        query = request.form.get("search_query", "").strip()

        if query and youtube:
            try:
                response = youtube.search().list(
                    q=query,
                    part="snippet",
                    type="video",
                    maxResults=3,
                ).execute()

                for item in response.get("items", []):
                    snippet = item["snippet"]
                    video_id = item["id"]["videoId"]
                    title = snippet.get("title", "")

                    image_path = download_thumbnail(
                        video_id,
                        snippet.get("thumbnails", {}),
                    )

                    if image_path is None:
                        log_result(
                            video_id,
                            title,
                            "ERROR",
                            error="Thumbnail download failed",
                        )
                        continue

                    classification, reason, raw, error = (
                        moderate_thumbnail(image_path)
                    )

                    # Log every attempted classification.
                    log_result(
                        video_id=video_id,
                        title=title,
                        classification=classification,
                        reason=reason,
                        raw_response=raw,
                        error=error,
                    )

                    # Fail closed: only explicitly SAFE results
                    # are allowed onto the page.
                    if classification != "SAFE":
                        continue

                    thumbnails = snippet.get("thumbnails", {})
                    medium_thumbnail = thumbnails.get("medium", {})
                    thumbnail_url = medium_thumbnail.get("url", "")

                    results.append({
                        "title": title,
                        "thumbnail": thumbnail_url,
                        "local_thumbnail": (
                            f"/thumbnails/{video_id}.jpg"
                        ),
                        "video_id": video_id,
                        "channel": snippet.get("channelTitle", ""),
                    })

            except Exception:
                app.logger.exception("YouTube search failed")

    return render_template(
        "index.html",
        query=query,
        results=results,
    )

@app.route("/thumbnails/<video_id>.jpg")
def serve_thumbnail(video_id):
    # Restrict filenames to expected YouTube video ID characters.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", video_id):
        return "Not found", 404

    from flask import send_from_directory

    return send_from_directory(
        str(THUMBNAIL_DIR.resolve()),
        f"{video_id}.jpg",
    )

if __name__ == "__main__":
    app.run(debug=True)