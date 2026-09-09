import os
import json
import re
import time
from typing import Optional, List, Dict
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
from app.models import ExtractionResponse, is_transient_error
from app.security import check_for_prompt_injection


# Load environment variables
load_dotenv()

SYSTEM_PROMPT_FILE = Path(__file__).parent / "prompts" / "claim_extraction_system.txt"
USER_PROMPT_FILE = Path(__file__).parent / "prompts" / "claim_extraction_user.txt"

def load_extraction_system_prompt() -> str:
    """Reads the extraction system prompt file at runtime."""
    if not SYSTEM_PROMPT_FILE.exists():
        legacy_file = Path(__file__).parent / "prompts" / "claim_extraction.txt"
        if legacy_file.exists():
            with open(legacy_file, "r", encoding="utf-8") as f:
                return f.read()
        raise FileNotFoundError(f"Extraction system prompt not found at {SYSTEM_PROMPT_FILE}")
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def load_extraction_user_prompt() -> str:
    """Reads the extraction user prompt template file at runtime."""
    if not USER_PROMPT_FILE.exists():
        raise FileNotFoundError(f"Extraction user prompt template not found at {USER_PROMPT_FILE}")
    with open(USER_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def clean_json_response(raw_text: str) -> str:
    """Extracts valid JSON string from potential markdown code block."""
    text = raw_text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text

def extract_claims(caption: str, api_key: Optional[str] = None) -> ExtractionResponse:
    """
    Extracts promotional claims and promoted site from caption text using Gemini LLM.
    Supports BYOK per-request API key with fallback to GEMINI_API_KEY environment variable.
    Includes exponential backoff retry for transient 429/5xx errors.
    Fails gracefully on retry exhaustion without crashing the caller.
    """
    if not caption or not caption.strip():
        return ExtractionResponse(promoted_site=None, claims=[])

    # Sanity check caption for prompt injection patterns
    check_for_prompt_injection(caption, source_identifier="caption_text")

    effective_api_key = (api_key.strip() if api_key and api_key.strip() else None) or os.getenv("GEMINI_API_KEY")
    if not effective_api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=effective_api_key)

    system_instruction = load_extraction_system_prompt()
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config={"response_mime_type": "application/json"}
    )

    user_template = load_extraction_user_prompt()
    user_prompt = user_template.replace("{caption}", caption)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = model.generate_content(user_prompt)

            raw_text = response.text or "{}"
            clean_json = clean_json_response(raw_text)
            data = json.loads(clean_json)

            if data.get("promoted_site") in ["", "null", "none", None]:
                data["promoted_site"] = None

            if "claims" in data and isinstance(data["claims"], list):
                from app.models import sanitize_category
                for item in data["claims"]:
                    if isinstance(item, dict):
                        item["category"] = sanitize_category(item.get("category"))

            return ExtractionResponse.model_validate(data)

        except Exception as e:
            if is_transient_error(e) and attempt < max_attempts - 1:
                time.sleep(2 ** (attempt + 1))  # Exponential backoff: 2s, 4s
                continue
            clean_err = re.sub(r'AIza[A-Za-z0-9_\-]{30,60}', '[REDACTED]', str(e))
            raise RuntimeError(f"Extraction service unavailable: {clean_err}")



