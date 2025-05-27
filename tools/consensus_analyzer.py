import re 
import json # Added for potential argument parsing in the future, and llm call response
from typing import Dict, List, Optional # Added for type hinting

# --- Tool Metadata ---
name = "consensus_analyzer"
emoji = "🧭"
description = "Analyzes a conversation (list of messages) to identify agreements, disagreements, sentiment, and provide a summary."
parameters = {
    "type": "object",
    "properties": {
        "messages": {
            "type": "array",
            "description": "A list of message objects, each with at least 'speaker' and 'text' keys.",
            # If you need to specify the type of items in the array, you can add an "items" field here.
            # For example:
            # "items": {
            #     "type": "object",
            #     "properties": {
            #         "speaker": {"type": "string"},
            #         "text": {"type": "string"}
            #     },
            #     "required": ["speaker", "text"]
            # }
        }
    },
    "required": ["messages"]
}

# --- Core Tool Logic ---

def parse_llm_response(llm_response_text: str) -> dict:
    """Parses the structured text response from the LLM."""
    analysis = {
        "summary": "Error parsing summary.",
        "sentiment": {"overall": "Error", "analysis": "Error parsing sentiment."},
        "agreements": ["Error parsing agreements."],
        "disagreements": ["Error parsing disagreements."]
    }

    try:
        # Use regex for potentially more robust parsing
        summary = re.search(r"Summary:(.*?)(?=Sentiment:|Agreements:|Disagreements:|$)", llm_response_text, re.DOTALL | re.IGNORECASE)
        sentiment_match = re.search(r"Sentiment:(.*?)(?=Agreements:|Disagreements:|$)", llm_response_text, re.DOTALL | re.IGNORECASE)
        agreements = re.search(r"Agreements:(.*?)(?=Disagreements:|$)", llm_response_text, re.DOTALL | re.IGNORECASE)
        disagreements = re.search(r"Disagreements:(.*)", llm_response_text, re.DOTALL | re.IGNORECASE)

        if summary:
            analysis["summary"] = summary.group(1).strip()

        if sentiment_match:
            sentiment_text = sentiment_match.group(1).strip()
            parts = sentiment_text.split('-', 1)
            if len(parts) == 2:
                analysis["sentiment"]["overall"] = parts[0].strip()
                analysis["sentiment"]["analysis"] = parts[1].strip()
            elif sentiment_text:
                 analysis["sentiment"]["overall"] = sentiment_text
                 analysis["sentiment"]["analysis"] = "Justification missing in response."
            else:
                 analysis["sentiment"]["overall"] = "Error"
                 analysis["sentiment"]["analysis"] = "Could not parse sentiment."


        if agreements:
            agreement_text = agreements.group(1).strip()
            if "No specific agreements identified." in agreement_text:
                 analysis["agreements"] = ["No specific agreements identified."]
            else:
                 # Extract list items, filtering out empty strings
                 analysis["agreements"] = [item.strip() for item in agreement_text.split('- ') if item.strip()]
                 if not analysis["agreements"] and agreement_text: # Handle case where text exists but no list items
                     analysis["agreements"] = [agreement_text]
                 elif not analysis["agreements"]: # Handle empty section
                     analysis["agreements"] = ["No specific agreements identified."]

        if disagreements:
            disagreement_text = disagreements.group(1).strip()
            if "No specific disagreements identified." in disagreement_text:
                 analysis["disagreements"] = ["No specific disagreements identified."]
            else:
                 # Extract list items, filtering out empty strings
                 analysis["disagreements"] = [item.strip() for item in disagreement_text.split('- ') if item.strip()]
                 if not analysis["disagreements"] and disagreement_text: # Handle case where text exists but no list items
                     analysis["disagreements"] = [disagreement_text]
                 elif not analysis["disagreements"]: # Handle empty section
                      analysis["disagreements"] = ["No specific disagreements identified."]

    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        # Keep default error messages in analysis dict if regex fails

    # Final check for empty sections that might have been missed
    if not analysis["agreements"] and "Agreements:" in llm_response_text:
         analysis["agreements"] = ["No specific agreements identified."]
    if not analysis["disagreements"] and "Disagreements:" in llm_response_text:
         analysis["disagreements"] = ["No specific disagreements identified."]


    return analysis


async def tool(roo, arguments: dict, user: str) -> dict:
    """
    Main function for the consensus analyzer tool.

    Args:
        roo: The main application object (passed by the framework), includes LLM client via roo.inference.
        arguments: A dictionary containing parameters passed to the tool.
                   Expected key: "messages".
        user: The user invoking the tool (passed by the framework).

    Returns:
        A dictionary containing the analysis result or an error message.
    """
    messages_input = arguments.get("messages")

    if not messages_input or not isinstance(messages_input, list):
        return {"error": "Missing or invalid 'messages' parameter. Expected a list of message objects."}

    # 1. Format messages for the prompt
    formatted_conversation = ""
    for msg in messages_input:
        # Add basic validation for message structure
        speaker = msg.get('speaker', 'Unknown')
        text = msg.get('text', '')
        if not text:
            continue # Skip messages without text
        formatted_conversation += f"{speaker}: {text}\\n---\\n"

    if not formatted_conversation:
         return {"error": "No valid messages found in the input list."}

    # 2. Define the Core Prompt
    core_prompt = f"""Analyze the following conversation thread:

<conversation>
{formatted_conversation}</conversation>

Based *only* on the text provided in the conversation, perform the following analysis:

1.  **Summary:** Provide a concise, neutral summary of the main topics discussed.
2.  **Sentiment:** Analyze the overall sentiment. Respond with one word: 'positive', 'negative', 'neutral', or 'mixed'. Then, provide a brief (1-2 sentence) justification for this assessment based on the language used.
3.  **Agreements:** List the key points or proposals where participants explicitly or implicitly showed agreement. Start each point with '- '. If no clear agreements are found, state "No specific agreements identified."
4.  **Disagreements:** List the key points or proposals where participants explicitly or implicitly showed disagreement or contention. Start each point with '- '. If no clear disagreements are found, state "No specific disagreements identified."
5.  **Suggested Next Steps:** Based on the above, propose 1–3 practical next steps the group could take to move forward constructively. Use short action phrases starting with a verb.

Present your response clearly sectioned using the headings: "Summary:", "Sentiment:", "Agreements:", "Disagreements:", "Suggested Next Steps:". Do not add any introductory or concluding remarks outside of these sections.
"""

    # 3. Call the LLM
    llm_messages = [{"role": "user", "content": core_prompt}]
    llm_response_text = None # Initialize
    try:
        # Access the LLM client via roo.inference
        # Note: Assuming roo.inference is the LLMClient instance
        if not hasattr(roo, 'inference') or not hasattr(roo.inference, 'invoke'):
             return {"error": "LLM client ('roo.inference.invoke') not available."}

        # Make the LLM call - no tools needed for this specific call
        llm_response = await roo.inference.invoke(messages=llm_messages, tools=None)

        # Extract the content from the response message
        if llm_response and isinstance(llm_response, dict) and "message" in llm_response:
            llm_response_text = llm_response["message"].get("content")
        elif llm_response and isinstance(llm_response, dict) and "content" in llm_response: # Handle direct content if 'message' key is missing
            llm_response_text = llm_response.get("content")
        else:
            # Log the unexpected response structure for debugging
            print(f"Unexpected LLM response structure: {llm_response}")
            return {"error": "Received an unexpected response structure from the LLM."}

        if not llm_response_text:
             return {"error": "LLM response did not contain any content."}

    except Exception as e:
        print(f"Error calling LLM: {e}")
        # Consider logging the full traceback here if needed: import traceback; traceback.print_exc()
        return {"error": f"Failed to get analysis from LLM. Details: {e}"}


    # 4. Parse the LLM Response
    try:
        analysis_result = parse_llm_response(llm_response_text)
    except Exception as e:
        print(f"Error during LLM response parsing: {e}")
        return {"error": f"Failed to parse the analysis response. Details: {e}"}


    # 5. Return Structured Data
    return analysis_result

