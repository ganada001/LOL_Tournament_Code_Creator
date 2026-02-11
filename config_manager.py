import json
import os
from dotenv import load_dotenv

CONFIG_FILE = "config.json"
ENV_FILE = ".env"

DEFAULT_CONFIG = {
    "provider_id": None,
    "last_tournament_id": None,
    "region": "KR",
    "theme": "Dark",
    "use_stub": True  # Default to Stub API for safety
}

def load_config():
    """Load configuration from config.json, falling back to defaults."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Ensure all keys exist
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config: {e}")

# API Key related functions removed for security compliance.
# All API requests are now routed through a secure backend (GAS).
