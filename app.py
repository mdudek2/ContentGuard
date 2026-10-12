import os
import requests
from flask import Flask, render_template, request
from googleapiclient.discovery import build
from dotenv import load_dotenv
from pathlib import Path

THUMBNAIL_DIR = Path("./thumbnails")
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

def download_thumbnail(video_id, thumbnails):
    """Download a thumbnail and return its local path."""
    # Prefer the largest available thumbnail.
    for size in ("maxres", "standard", "high", "medium", "default"):
        thumbnail = thumbnails.get(size)

        if not thumbnail:
            continue

        try:
            response = requests.get(
                thumbnail["url"],
                timeout=10
            )
            response.raise_for_status()

            # Save using the video ID to avoid filename collisions.
            file_path = THUMBNAIL_DIR / f"{video_id}.jpg"
            file_path.write_bytes(response.content)

            return f"thumbnails/{video_id}.jpg"

        except requests.RequestException:
            continue

    return None

# Load variables from .env file into environment
load_dotenv()

app = Flask(__name__)

# Retrieve API key from environment
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize the YouTube service client
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

@app.route("/", methods=["GET", "POST"])
def index():
    query = ""
    results = []
    
    if request.method == "POST":
        query = request.form.get("search_query", "").strip()
        
        if query and YOUTUBE_API_KEY:
            # Query the YouTube Data API v3
            response = youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=10
            ).execute()
            
            # Extract video metadata
            for item in response.get("items", []):
                snippet = item["snippet"]
                video_id = item["id"]["videoId"]

                local_thumbnail = download_thumbnail(
                    video_id,
                    snippet.get("thumbnails", {})
                )

                video_data = {
                    "title": snippet["title"],
                    "thumbnail": snippet["thumbnails"]["medium"]["url"],
                    "local_thumbnail": local_thumbnail,
                    "video_id": video_id,
                    "channel": snippet["channelTitle"]
                }

                results.append(video_data)
            
    return render_template("index.html", query=query, results=results)

if __name__ == "__main__":
    app.run(debug=True)