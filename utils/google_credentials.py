"""Utility functions for Google credentials handling."""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def decode_google_credentials(env_var_name: str) -> Optional[Dict[str, Any]]:
    """
    Decode base64-encoded Google credentials from an environment variable.

    Args:
        env_var_name: Name of the environment variable containing base64-encoded credentials

    Returns:
        Dictionary containing the decoded credentials, or None if not found or invalid
    """
    encoded_creds = os.getenv(env_var_name)
    if not encoded_creds:
        return None

    try:
        decoded_creds = json.loads(base64.b64decode(encoded_creds).decode())
        logger.debug(f"Successfully loaded credentials from {env_var_name}")
        return decoded_creds
    except Exception as e:
        logger.error(f"Error decoding credentials from {env_var_name}: {e}")
        return None


def load_all_google_credentials() -> Dict[str, Any]:
    """
    Load all Google credentials from environment variables.

    Returns:
        Dictionary containing all decoded Google credentials with keys:
        - google_creds: General Google credentials (for Sheets, etc.)
        - google_docs_creds: Google Docs specific credentials
    """
    config = {}

    # Load general Google credentials (for Sheets)
    if google_creds := decode_google_credentials("GOOGLE_CREDENTIALS"):
        config["google_creds"] = google_creds

    # Load Google Docs credentials
    if google_docs_creds := decode_google_credentials("GOOGLE_DOCS_CREDENTIALS"):
        config["google_docs_creds"] = google_docs_creds

    # Load Google Docs API key (simple string - for public docs)
    if google_docs_api_key := os.getenv("GOOGLE_DOCS_API_KEY"):
        config["google_docs_api_key"] = google_docs_api_key
        logger.debug("Successfully loaded Google Docs API key")

    return config
