import os

DEFAULT_BASE_URL = "http://10.32.2.11:35000/v1"
DEFAULT_MODEL = "qwen3.8-27b"

def get_api_token():
    token = os.getenv("API_TOKEN")
    return token

def get_base_url():
    return os.getenv("BASE_URL", DEFAULT_BASE_URL)

def get_model_name():
    return os.getenv("MODEL", DEFAULT_MODEL)