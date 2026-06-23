import json
import os
import hashlib
from urllib.parse import urlparse

import client_settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "LOL_Tournament_Code_Creator"
LEGACY_CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DEFAULT_APP_DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_APP_DATA_DIR, "config.json")
CONFIG_FILE = DEFAULT_CONFIG_FILE
TOURNAMENT_ROUTING_VALUES = {"americas", "asia", "europe", "sea"}

DEFAULT_CONFIG = {
    "api_key": "",
    "provider_id": None,
    "last_tournament_id": None,
    "region": "KR",
    "routing_value": "americas",
    "api_transport": "supabase",
    "supabase_url": "",
    "supabase_anon_key": "",
    "supabase_client_id": "",
    "supabase_access_token": "",
    "supabase_refresh_token": "",
    "supabase_user_email": "",
    "theme": "Dark",
    "use_stub": True
}

ALLOWED_CONFIG_KEYS = set(DEFAULT_CONFIG)


def load_config():
    """Load configuration from config.json, falling back to defaults."""
    if not os.path.exists(CONFIG_FILE):
        initial_config = _load_legacy_config() or DEFAULT_CONFIG.copy()
        save_config(initial_config)
        return normalize_config(initial_config)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("Config root must be an object")
            config = DEFAULT_CONFIG.copy()
            config.update(loaded)
            return normalize_config(config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return normalize_config(DEFAULT_CONFIG.copy())


def _load_legacy_config():
    if os.path.abspath(CONFIG_FILE) != os.path.abspath(DEFAULT_CONFIG_FILE):
        return None
    if not os.path.exists(LEGACY_CONFIG_FILE):
        return None
    try:
        with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def normalize_config(config):
    raw_config = DEFAULT_CONFIG.copy()
    if isinstance(config, dict):
        raw_config.update(config)
    normalized = {
        key: raw_config.get(key, DEFAULT_CONFIG[key])
        for key in ALLOWED_CONFIG_KEYS
    }

    normalized["region"] = str(normalized.get("region") or "KR").upper()
    normalized["routing_value"] = str(normalized.get("routing_value") or "americas").lower()
    if normalized["routing_value"] not in TOURNAMENT_ROUTING_VALUES:
        normalized["routing_value"] = "americas"

    normalized["api_transport"] = "supabase"

    supabase_settings = get_supabase_client_settings()
    normalized["supabase_url"] = supabase_settings["supabase_url"]
    normalized["supabase_anon_key"] = supabase_settings["supabase_anon_key"]
    normalized["supabase_client_id"] = str(normalized.get("supabase_client_id") or "").strip()
    normalized["supabase_access_token"] = str(normalized.get("supabase_access_token") or "").strip()
    normalized["supabase_refresh_token"] = str(normalized.get("supabase_refresh_token") or "").strip()
    normalized["supabase_user_email"] = str(normalized.get("supabase_user_email") or "").strip()
    normalized["use_stub"] = bool(normalized.get("use_stub", True))
    return normalized


def get_supabase_client_settings():
    return {
        "supabase_url": client_settings.get_supabase_project_url(),
        "supabase_anon_key": client_settings.get_supabase_anon_key(),
        "supabase_function_name": client_settings.get_supabase_function_name(),
    }


def get_supabase_client_id(settings=None):
    settings = settings or get_supabase_client_settings()
    supabase_url = settings.get("supabase_url", "")
    supabase_anon_key = settings.get("supabase_anon_key", "")
    if not supabase_url or not supabase_anon_key:
        return ""
    digest = hashlib.sha256(f"{supabase_url}\n{supabase_anon_key}".encode("utf-8")).hexdigest()
    return digest[:16]


def save_config(config):
    """Save configuration to config.json."""
    try:
        safe_config = normalize_config(config)
        safe_config["api_key"] = ""
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        tmp_file = f"{CONFIG_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(safe_config, f, indent=4, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_file, CONFIG_FILE)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def is_valid_supabase_url(supabase_url):
    parsed = urlparse((supabase_url or "").strip().rstrip("/"))
    return parsed.scheme == "https" and bool(parsed.netloc)


def production_config_warnings(config=None):
    config = normalize_config(config or load_config())
    current_client_id = get_supabase_client_id()
    warnings = []
    if not is_valid_supabase_url(config.get("supabase_url")):
        warnings.append("Supabase Project URL is missing or invalid in client_settings.py.")
    if not config.get("supabase_anon_key"):
        warnings.append("Supabase anon key is missing in client_settings.py.")
    if not config.get("supabase_access_token"):
        warnings.append("Operator authentication is required.")
    elif current_client_id and config.get("supabase_client_id") != current_client_id:
        warnings.append("Operator authentication must be renewed for this Supabase backend.")
    if config.get("routing_value") not in TOURNAMENT_ROUTING_VALUES:
        warnings.append("Riot regional routing value is invalid.")
    return warnings
