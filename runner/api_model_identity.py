"""Resolve a user-configured API model ID without selecting a provider."""
import os
def api_model_id(model):
    return os.environ.get('ICLWORLD_API_MODEL_ID') or model
