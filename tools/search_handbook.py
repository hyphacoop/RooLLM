import aiohttp
from bs4 import BeautifulSoup
from lunr import lunr
from typing import List
import html
import json

name = "search_handbook"
description = "Search the Hypha handbook for a given query."
parameters = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search term to look for in the handbook."
        }
    },
    "required": ["query"]
}

SEARCH_INDEX_URL = "https://handbook.hypha.coop/search_index.json"
HANDBOOK_BASE_URL = "https://handbook.hypha.coop/"


# Helper Functions
async def fetch_search_index() -> dict:
    """Fetch the handbook search index as JSON."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SEARCH_INDEX_URL) as response:
                if response.status == 200:
                    return await response.json()
                print(f"Failed to fetch search index: HTTP {response.status}")
        except aiohttp.ClientError as e:
            print(f"Error fetching search index: {e}")
    return {}


def sanitize_content(content: str) -> str:
    """Clean up and sanitize HTML content."""
    return html.escape(content.strip())


def load_lunr_index(index_data: dict) -> lunr:
    """Create a Lunr search index from the fetched index data."""
    try:
        fields = ["title", "keywords", "body"]
        document_store = index_data.get("index", {}).get("documentStore", {}).get("store", {})
        documents = [
            {"url": url, "title": "", "keywords": "", "body": " ".join(tokens)}
            for url, tokens in document_store.items()
        ]
        return lunr(ref="url", fields=fields, documents=documents)
    except Exception as e:
        print(f"Error loading Lunr index: {e}")
        return None


async def fetch_page_content(url: str) -> str:
    """Fetch and extract content from a handbook page."""
    full_url = HANDBOOK_BASE_URL + url
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(full_url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    section = soup.find("section", class_="normal markdown-section")
                    if section:
                        return sanitize_content(section.get_text(separator="\n").strip())
                print(f"No content found at {full_url}.")
        except aiohttp.ClientError as e:
            print(f"Error fetching page content: {e}")
    return None


def prioritize_results(results: List[str], keywords: List[str]) -> List[str]:
    """Prioritize URLs that match query keywords."""
    keywords = [keyword.lower() for keyword in keywords]
    prioritized = [url for url in results if any(keyword in url.lower() for keyword in keywords)]
    non_prioritized = [url for url in results if url not in prioritized]

    return prioritized + non_prioritized


# Main Tool Logic
async def tool(roo, arguments):
    query = arguments["query"]
    extracted_page_count = 0
    parsed_steps = []  # For tracking steps and intermediate results
    final_response = None

    # We'll accumulate "status" or "debug" messages here.
    status_messages: List[str] = []

    status_messages.append(f"Starting handbook search for query: '{query}'")

    # Step 1: Fetch search index
    search_index = await fetch_search_index(status_messages)    
    if not search_index:
        status_messages.append("The handbook search index is currently unavailable.")
        return "\n".join(status_messages)

    # Step 2: Load Lunr index
    lunr_index = load_lunr_index(search_index, status_messages)
    if not lunr_index:
        status_messages.append("Failed to load the handbook search index.")
        return "\n".join(status_messages)

    # Step 3: Perform search
    try:
        results = lunr_index.search(query)
        if not results:
            status_messages.append("No relevant results found in the handbook.")
            return "\n".join(status_messages)

        # Extract and prioritize URLs
        urls = [result["ref"] for result in results]
        prioritized_urls = prioritize_results(urls, query.split())

        # Step 4: Iteratively search and refine results
        for url in prioritized_urls:

            if final_response:  # Exit the loop if a satisfactory response is found
                break

            page_content = await fetch_page_content(url, status_messages)
            if page_content:
                extracted_page_count += 1

                # JSON-formatted prompt for LLM
                combined_prompt = json.dumps({
                    "retrieved_content": page_content,
                    "original_query": query,
                    "source_url": f"{HANDBOOK_BASE_URL}{url}",
                    "instruction": (
                        "You are a JSON-producing assistant. Return only valid JSON following this schema:\n\n"
                        "{\n"
                        "  \"steps\": [\n"
                        "    {\n"
                        "      \"function\": \"string\",\n"
                        "      \"parameters\": {\"key1\": \"value1\", ...},\n"
                        "      \"human_readable_justification\": \"string\"\n"
                        "    },\n"
                        "    ...\n"
                        "  ],\n"
                        "  \"done\": \"string or null\"\n"
                        "}\n\n"
                        "Do not include any markdown code fences or extra text. Output must be valid JSON.\n"
                        "If you do NOT have a sufficient answer, keep 'done' as null.\n"
                        "If you DO have a sufficient answer, place it in 'done' and explicitly include:\n"
                        " - The source URL\n"
                        " - The number of pages consulted so far\n"
                        "Make sure that 'done' contains the final answer, the source URL, "
                        f"and the string 'Pages consulted: {extracted_page_count}'."
                    )
                })

                # Multi-turn interaction with the LLM
                response = await roo.inference(
                    [{"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": combined_prompt}]
                )

                # Parse LLM response
                llm_output = response.get("content", "")
                try:
                    llm_response = json.loads(llm_output)

                       # Extract `done` and steps
                    steps = llm_response.get("steps", [])
                    if steps:
                        parsed_steps.extend(steps)
                
                    # Check if the LLM indicates a final answer
                    final_answer_candidate = llm_response.get("done")
                    if final_answer_candidate:  # If not null, we consider it 'sufficient'
                        final_response = final_answer_candidate
                        status_messages.append(
                            f"Satisfactory final answer found after consulting {extracted_page_count} page(s)."
                        )
                        break

                except json.JSONDecodeError:
                    status_messages.append(
                        f"Invalid JSON response from LLM: {llm_output}"
                    )
                    continue
            else:
                status_messages.append(f"Could not extract content from {url}")

        # Step 5: Finalize response
        if final_response:
            # Return exactly the final text from the LLM
            return final_response
        else:
            status_messages.append(f"No satisfactory content was found in the handbook at {url}")
            return "\n".join(status_messages)

    except Exception as e:
        status_messages.append(f"Error during handbook search: {e}")
        return "\n".join(status_messages)
