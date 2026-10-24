import os
import sys

os.environ["APP_TODAY"] = "2026-10-24"
os.environ["DB_PATH"] = ":memory:"
os.environ.pop("LLM_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
