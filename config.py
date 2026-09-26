# Urch/config.py
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def get_env_var(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Variable '{key}' not found in .env")
    return value
    
def get_env_int(key: str) -> int:
    val = get_env_var(key).strip()
    if not val.isdigit():
        raise ValueError(f"Variable '{key}' must be a valid integer, got '{val}'")
    return int(val)

BOT_TOKEN = get_env_var('BOT_TOKEN')
GROQ_API_KEY  = get_env_var('GROQ_API_KEY')
POLLINATIONS_API_KEY = get_env_var('POLLINATIONS_API_KEY')
GOOGLE_API_KEY = get_env_var('GOOGLE_API_KEY')