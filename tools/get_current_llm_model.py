name = "get_current_llm_model"
emoji = "🎯"
description = "Return the identifier of the LLM model currently configured for RooLLM invocations."

parameters = {
    "type": "object",
    "properties": {},
    "required": []
}


async def tool(roo, arguments, user):
    """Return the model name currently set on RooLLM's inference client."""
    llm_client = getattr(roo, "inference", None)
    if llm_client is None:
        return {"error": "RooLLM is missing an LLM client instance."}

    model_name = getattr(llm_client, "model", None)
    if not model_name:
        return {"error": "No model is configured."}

    return {"model": model_name} 