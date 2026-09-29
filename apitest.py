import os

from dotenv import load_dotenv
from googleapiclient.discovery import build


# Load variables from .env in the project root
load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "YOUTUBE_API_KEY is not set. "
        "Make sure it exists in your .env file."
    )


youtube = build(
    "youtube",
    "v3",
    developerKey=API_KEY,
)

request = youtube.search().list(
    part="snippet",
    q="Python tutorial",
    type="video",
    maxResults=5,
)

response = request.execute()

for item in response["items"]:
    title = item["snippet"]["title"]
    video_id = item["id"]["videoId"]

    print(title)
    print(f"https://www.youtube.com/watch?v={video_id}")
    print()
