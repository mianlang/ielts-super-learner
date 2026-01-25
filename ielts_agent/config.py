"""Configuration management for IELTS Agent."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use env vars only

# API Configuration
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")


def get_api_key() -> str:
    """
    Get the API key, raising an error if not set.

    Returns:
        The ZHIPUAI API key

    Raises:
        ValueError: If API key is not configured
    """
    if not ZHIPUAI_API_KEY:
        raise ValueError(
            "ZHIPUAI_API_KEY not found. Please set it in your .env file. "
            "Get your API key from: https://open.bigmodel.cn/usercenter/apikeys"
        )
    return ZHIPUAI_API_KEY

# BigModel API Configuration
ZHIPUAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4-flash"  # Fast and cost-effective
ALTERNATIVE_MODEL = "glm-4-plus"  # Higher quality for scoring

# Project Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = DATA_DIR / "ielts.db"

# IELTS Skills
SKILLS = ["listening", "reading", "writing", "speaking"]

# Writing Tasks
WRITING_TASKS = [1, 2]

# Speaking Parts
SPEAKING_PARTS = [1, 2, 3]

# Band Scores
BAND_SCORES = list(range(10))  # 0-9

# Assessment Criteria for Writing
WRITING_CRITERIA = [
    "Task Achievement / Task Response",
    "Coherence and Cohesion",
    "Lexical Resource",
    "Grammatical Range and Accuracy",
]

# Assessment Criteria for Speaking
SPEAKING_CRITERIA = [
    "Fluency and Coherence",
    "Lexical Resource",
    "Grammatical Range and Accuracy",
    "Pronunciation",
]
