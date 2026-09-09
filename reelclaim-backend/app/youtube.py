import os
import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
from pydantic import BaseModel, Field

import requests

logger = logging.getLogger("reelclaim.youtube")

class YouTubeIngestResult(BaseModel):
    video_id: str
    video_url: str
    title: str = ""
    description: str = ""
    channel_title: str = ""
    thumbnail_url: Optional[str] = None
    transcript: str = ""
    combined_text: str = ""
    detected_site: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Extracts the YouTube 11-character video ID from various YouTube URL structures:
    - https://www.youtube.com/shorts/3f5G8kL9XYZ
    - https://youtube.com/shorts/3f5G8kL9XYZ?feature=share
    - https://www.youtube.com/watch?v=3f5G8kL9XYZ
    - https://youtu.be/3f5G8kL9XYZ
    - https://m.youtube.com/watch?v=3f5G8kL9XYZ
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()

    # Pattern for shorts: /shorts/<id>
    shorts_match = re.search(r'(?:youtube\.com|youtu\.be)/shorts/([a-zA-Z0-9_-]{11})', url)
    if shorts_match:
        return shorts_match.group(1)

    # Pattern for youtu.be/<id>
    youtu_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if youtu_match:
        return youtu_match.group(1)

    # Pattern for watch?v=<id>
    watch_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if watch_match:
        return watch_match.group(1)

    # Pattern for embed or direct 11-char ID
    embed_match = re.search(r'(?:youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})', url)
    if embed_match:
        return embed_match.group(1)

    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    return None

def is_youtube_url(url: str) -> bool:
    """Returns True if the string looks like a YouTube URL or YouTube Shorts URL."""
    if not url or not isinstance(url, str):
        return False
    lower = url.lower()
    return "youtube.com" in lower or "youtu.be" in lower or extract_youtube_video_id(url) is not None

def extract_promoted_urls_from_text(text: str) -> List[str]:
    """
    Extracts third-party promoted website URLs from description or transcript text.
    Filters out common social media platforms (youtube, instagram, twitter, etc.).
    """
    if not text:
        return []
    
    # URL extraction regex
    url_pattern = r'https?://[^\s<>"\')]+'
    matches = re.findall(url_pattern, text)
    
    excluded_domains = {
        "youtube.com", "youtu.be", "google.com", "instagram.com", "twitter.com",
        "x.com", "facebook.com", "tiktok.com", "linkedin.com", "reddit.com"
    }

    valid_urls = []
    for u in matches:
        cleaned = u.rstrip(".,;!?:")
        try:
            parsed = urlparse(cleaned)
            netloc = parsed.netloc.replace("www.", "").lower()
            if netloc and not any(netloc == exc or netloc.endswith(f".{exc}") for exc in excluded_domains):
                valid_urls.append(cleaned)
        except Exception:
            continue

    return list(dict.fromkeys(valid_urls))

def fetch_youtube_metadata(video_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches video metadata (title, description, channel, thumbnail).
    Prioritizes YouTube Data API v3 if key is provided or found in environment,
    with automatic graceful fallback to public oEmbed API and yt-dlp.
    """
    key = api_key or os.environ.get("YOUTUBE_API_KEY")
    result = {
        "title": "",
        "description": "",
        "channel_title": "",
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    }

    # Strategy 1: Official YouTube Data API v3 (if key provided)
    if key and key.strip():
        try:
            api_url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet",
                "id": video_id,
                "key": key.strip()
            }
            resp = requests.get(api_url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    snippet = items[0].get("snippet", {})
                    result["title"] = snippet.get("title", "")
                    result["description"] = snippet.get("description", "")
                    result["channel_title"] = snippet.get("channelTitle", "")
                    thumbs = snippet.get("thumbnails", {})
                    if "maxres" in thumbs:
                        result["thumbnail_url"] = thumbs["maxres"].get("url")
                    elif "high" in thumbs:
                        result["thumbnail_url"] = thumbs["high"].get("url")
                    elif "default" in thumbs:
                        result["thumbnail_url"] = thumbs["default"].get("url")
                    logger.info(f"Retrieved YouTube metadata via Data API v3 for {video_id}")
                    return result
            else:
                logger.warning(f"YouTube Data API returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"YouTube Data API request error ({e}). Falling back to oEmbed.")

    # Strategy 2: YouTube oEmbed endpoint (Free, no auth, lightweight)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(oembed_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if not result["title"]:
                result["title"] = data.get("title", "")
            if not result["channel_title"]:
                result["channel_title"] = data.get("author_name", "")
            if "thumbnail_url" in data:
                result["thumbnail_url"] = data.get("thumbnail_url")
            logger.info(f"Retrieved YouTube metadata via oEmbed for {video_id}")
    except Exception as e:
        logger.warning(f"oEmbed metadata lookup failed: {e}")

    # Strategy 3: yt-dlp metadata extraction if description is still empty
    if not result["description"]:
        try:
            import yt_dlp
            ydl_opts = {
                'skip_download': True,
                'extract_flat': False,
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if info:
                    if not result["title"]:
                        result["title"] = info.get("title", "")
                    result["description"] = info.get("description", "")
                    if not result["channel_title"]:
                        result["channel_title"] = info.get("uploader", "") or info.get("channel", "")
                    if info.get("thumbnail"):
                        result["thumbnail_url"] = info.get("thumbnail")
        except Exception as ytdl_err:
            logger.debug(f"yt-dlp metadata lookup note: {ytdl_err}")

    return result

def fetch_youtube_transcript(video_id: str) -> str:
    """
    Fetches auto-generated or creator-uploaded transcripts/captions without OAuth.
    Uses youtube-transcript-api with fallback to yt-dlp subtitle extraction.
    """
    transcript_text = ""

    # Strategy 1: youtube-transcript-api (Fast, pure Python, direct API)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        ytt = YouTubeTranscriptApi() if isinstance(YouTubeTranscriptApi, type) else None

        # Try ytt.fetch or static fetch/get_transcript
        try:
            if ytt and hasattr(ytt, "fetch"):
                fetched = ytt.fetch(video_id, languages=('en', 'en-US', 'en-GB', 'hi', 'auto'))
                texts = []
                for item in fetched:
                    t = getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
                    if t:
                        texts.append(t.strip())
                transcript_text = " ".join(texts)
            elif hasattr(YouTubeTranscriptApi, "get_transcript"):
                chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB', 'hi'])
                texts = [item.get("text", "").strip() for item in chunks if isinstance(item, dict) and item.get("text")]
                transcript_text = " ".join(texts)

            if transcript_text:
                logger.info(f"Successfully retrieved transcript ({len(transcript_text)} chars) for {video_id}")
                return transcript_text
        except Exception as primary_err:
            logger.info(f"Primary transcript fetch attempt for {video_id}: {primary_err}")

        # Fallback to ytt.list() or list_transcripts
        try:
            list_func = getattr(ytt, "list", None) or getattr(YouTubeTranscriptApi, "list_transcripts", None)
            if list_func:
                t_list = list_func(video_id)
                for t in t_list:
                    fetched = t.fetch()
                    texts = []
                    for item in fetched:
                        t_str = getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
                        if t_str:
                            texts.append(t_str.strip())
                    transcript_text = " ".join(texts)
                    if transcript_text:
                        return transcript_text
        except Exception as list_err:
            logger.warning(f"Transcript list fallback for {video_id}: {list_err}")

    except ImportError:
        logger.warning("youtube_transcript_api is not installed.")

    # Strategy 2: yt-dlp subtitle extraction
    if not transcript_text:
        try:
            import yt_dlp
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en.*', 'en', 'hi'],
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if info:
                    subtitles = info.get("subtitles") or info.get("automatic_captions") or {}
                    for lang, sub_entries in subtitles.items():
                        if lang.startswith("en") or lang.startswith("hi"):
                            for entry in sub_entries:
                                sub_url = entry.get("url")
                                if sub_url:
                                    try:
                                        resp = requests.get(sub_url, timeout=5)
                                        if resp.status_code == 200:
                                            clean_text = re.sub(r'<[^>]+>', '', resp.text)
                                            clean_text = re.sub(r'WEBVTT.*?\n', '', clean_text, flags=re.DOTALL)
                                            clean_text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', clean_text)
                                            lines = [line.strip() for line in clean_text.splitlines() if line.strip() and not line.strip().isdigit()]
                                            transcript_text = " ".join(lines)
                                            if transcript_text:
                                                logger.info(f"Retrieved transcript via yt-dlp subtitle URL for {video_id}")
                                                return transcript_text
                                    except Exception:
                                        continue
        except Exception as ytdl_err:
            logger.debug(f"yt-dlp transcript extraction error: {ytdl_err}")

    return transcript_text

def ingest_youtube_short(video_url: str, api_key: Optional[str] = None) -> YouTubeIngestResult:
    """
    High-level orchestrator:
    1. Extracts video ID from YouTube Short or Video URL.
    2. Fetches metadata (title, description, author, thumbnail).
    3. Fetches audio transcript / captions.
    4. Auto-detects promoted site URL.
    5. Assembles combined textual corpus for claim extraction.
    """
    video_id = extract_youtube_video_id(video_url)
    if not video_id:
        return YouTubeIngestResult(
            video_id="",
            video_url=video_url,
            status="error",
            error_message=f"Could not parse valid YouTube video ID from URL: {video_url}"
        )

    clean_video_url = f"https://www.youtube.com/shorts/{video_id}"
    metadata = fetch_youtube_metadata(video_id, api_key=api_key)
    transcript = fetch_youtube_transcript(video_id)

    # Detect promoted URLs in description, title, or transcript
    combined_raw = f"{metadata.get('title', '')}\n{metadata.get('description', '')}\n{transcript}"
    detected_links = extract_promoted_urls_from_text(combined_raw)
    detected_site = detected_links[0] if detected_links else None

    # Assemble structured combined text for claim extraction
    combined_parts = []
    if metadata.get("title"):
        combined_parts.append(f"Video Title: {metadata['title']}")
    if metadata.get("channel_title"):
        combined_parts.append(f"Channel: {metadata['channel_title']}")
    if metadata.get("description"):
        combined_parts.append(f"Description:\n{metadata['description']}")
    if transcript:
        combined_parts.append(f"Audio Transcript:\n{transcript}")
    elif not metadata.get("description") and not metadata.get("title"):
        combined_parts.append("No video metadata or transcript could be extracted.")

    combined_text = "\n\n".join(combined_parts)

    status = "success"
    if not transcript and not metadata.get("title") and not metadata.get("description"):
        status = "error"
    elif not transcript:
        status = "no_transcript"

    return YouTubeIngestResult(
        video_id=video_id,
        video_url=clean_video_url,
        title=metadata.get("title", ""),
        description=metadata.get("description", ""),
        channel_title=metadata.get("channel_title", ""),
        thumbnail_url=metadata.get("thumbnail_url"),
        transcript=transcript,
        combined_text=combined_text,
        detected_site=detected_site,
        status=status
    )
