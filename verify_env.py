"""
verify_env.py — Run this after activating your venv to confirm .env loads correctly.
Usage: python verify_env.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL", "NOT SET")
print(f"SUPABASE_URL = {url}")
assert url != "NOT SET" and not url.startswith("https://your"), (
    "Fill in .env with real values before running the app."
)
print("✓ .env loaded successfully.")
