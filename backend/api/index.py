import sys
import os

# Add parent directory to path so FastAPI can find main, groq_service, models, etc.
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from main import app
