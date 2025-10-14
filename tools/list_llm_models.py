name = "list_llm_models"
emoji = "📜"
description = "List the names of all LLM models currently installed on the configured Roo LLM / Ollama server."

parameters = {
    "type": "object",
    "properties": {},
    "required": []
}

import aiohttp
import logging

logger = logging.getLogger(__name__)

async def tool(roo, arguments, user):
    """Return a list of available models reported by the LLM backend.

    Args:
        roo: The active RooLLM instance.
        arguments: Unused – kept to satisfy the tool signature.
        user: The user invoking the tool (unused).

    Returns:
        dict: {"models": [str, ...]} on success or {"error": str} on failure.
    """
    try:
        llm_client = getattr(roo, "inference", None)
        if llm_client is None:
            return {"error": "RooLLM is missing an LLM client instance."}

        base_url = getattr(llm_client, "base_url", None)
        if not base_url:
            return {"error": "LLM client base URL not configured."}

        tags_url = f"{base_url.rstrip('/')}/api/tags"

        async with aiohttp.ClientSession(auth=llm_client.auth) as session:
            async with session.get(tags_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m.get("name") if isinstance(m, dict) else m for m in data.get("models", [])]
                    return {"models": models, "count": len(models)}
                body = await resp.text()
                logger.error("list_llm_models: failed %s %s", resp.status, body)
                return {"error": f"Failed to fetch models: {resp.status}"}
    except Exception as e:
        logger.exception("list_llm_models: exception")
        return {"error": str(e)} 