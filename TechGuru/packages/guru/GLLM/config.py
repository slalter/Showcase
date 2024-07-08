import os

def get_api_key():
    # Get the API key from an environment variable
    api_key = os.environ.get("OPENAI_KEY", "")

    return api_key

def get_logging_path():
    path = os.environ.get("GLLM_LOGGING_PATH", "")
    return path

def get_default_model():
    model = os.environ.get("DEFAULT_MODEL")
    return model if model else 'gpt-4-1106-preview'