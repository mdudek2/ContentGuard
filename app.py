import os
from flask import Flask, render_template, request
from googleapiclient.discovery import build
from dotenv import load_dotenv

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
                video_data = {
                    "title": snippet["title"],
                    "thumbnail": snippet["thumbnails"]["medium"]["url"],
                    "video_id": item["id"]["videoId"],
                    "channel": snippet["channelTitle"]
                }
                results.append(video_data)
            
    return render_template("index.html", query=query, results=results)

if __name__ == "__main__":
    app.run(debug=True)