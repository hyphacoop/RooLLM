import logging
import json
import os
import aiohttp
from dotenv import load_dotenv
import asyncio
import time
import re

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class MinimaRestAdapter:
    """
    Adapter for connecting to a Minima indexer using its REST API.
    
    This adapter allows RooLLM to communicate with the Minima indexer
    to search and retrieve information from local documents.
    """
    
    def __init__(self, server_url=None, config=None):
        """
        Initialize the Minima REST adapter.
        
        Args:
            server_url: URL of the Minima indexer server
            config: Configuration dictionary that may contain MINIMA_MCP_SERVER_URL and USE_MINIMA_MCP
        """
        # First try to get URL from config, then from env var, then default
        self.server_url = (
            config.get("MINIMA_MCP_SERVER_URL") if config else None
        ) or server_url or os.getenv("MINIMA_MCP_SERVER_URL", "http://localhost:8001")
        
        # Check if Minima is enabled (from config or env var)
        config_minima = config.get("USE_MINIMA_MCP") if config else None
        env_minima = os.getenv("USE_MINIMA_MCP", "false").lower() == "true"
        
        # If config value exists, convert it to bool, otherwise use env value
        self.using_minima = bool(config_minima) if config_minima is not None else env_minima
        
        self.connected = False
        self.tools = {}
        self.last_connection_attempt = 0
        self.connection_retry_interval = 10  # seconds
        
        # Define available tools
        self.tools = {
            "query": {
                "name": "query",
                "description": (
                    "Find information in local files (PDF, CSV, DOCX, MD, TXT). "
                    "This tool will return a JSON string in the 'content' field of the tool message. "
                    "The JSON will have the following structure: "
                    "{\"retrieved_content\": \"textual content found...\", \"citations\": [{\"original_source\": \"...\", \"formatted_citation\": \"[Source: ...]\", \"rule_applied\": \"...\"}]} "
                    "Use the 'retrieved_content' field to formulate your answer. "
                    "ALWAYS cite your sources using the 'formatted_citation' from each object in the 'citations' array. "
                    "Failing to cite sources is a critical error. Every response MUST include at least one source citation if information is used from 'retrieved_content'."
                ),
                "emoji": "🧠",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to search for in the documents"
                        }
                    },
                    "required": ["text"]
                }
            }
        }
        
    async def connect(self, force=False):
        """
        Connect to the Minima indexer server.
        
        Args:
            force: Force reconnection even if already connected or recently tried
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        # If already connected and not forcing reconnection, return true
        if self.connected and not force:
            return True
            
        # Avoid spamming connection attempts
        current_time = time.time()
        if not force and (current_time - self.last_connection_attempt) < self.connection_retry_interval:
            logger.info(f"Skipping connection attempt (tried {int(current_time - self.last_connection_attempt)}s ago)")
            return False
            
        self.last_connection_attempt = current_time
        
        try:
            # Test connection to the server with a simple query
            logger.debug(f"Attempting to connect to Minima at {self.server_url}")
            test_payload = {"query": "test"}
            
            # Make sure the server URL has the correct format
            server_url = self.server_url
            if not server_url.startswith(("http://", "https://")):
                server_url = f"http://{server_url}"
                
            # Ensure the server URL doesn't end with a slash
            server_url = server_url.rstrip('/')
            
            # Add retry logic for connection
            max_retries = 3
            retry_delay = 2  # seconds
            connection_timeout = 30  # increased timeout to 30 seconds
            
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.post(
                                f"{server_url}/query", 
                                json=test_payload,
                                timeout=connection_timeout
                            ) as response:
                                if response.status == 200:
                                    logger.debug(f"Successfully connected to Minima indexer at {server_url}")
                                    
                                    # Update the server URL if it was corrected
                                    self.server_url = server_url
                                    self.connected = True
                                    return True
                                else:
                                    error_text = await response.text()
                                    logger.error(f"Failed to connect to Minima indexer: {response.status}")
                                    logger.error(f"Error response: {error_text}")
                                    self.connected = False
                                    if attempt < max_retries - 1:
                                        logger.info(f"Retrying connection in {retry_delay} seconds...")
                                        await asyncio.sleep(retry_delay)
                                        continue
                                    return False
                        except aiohttp.ClientConnectorError as e:
                            logger.error(f"Could not connect to Minima server: {e}")
                            self.connected = False
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying connection in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                continue
                            return False
                        except asyncio.TimeoutError:
                            logger.error(f"Connection to Minima server timed out (attempt {attempt + 1}/{max_retries})")
                            self.connected = False
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying connection in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                continue
                            return False
                except Exception as e:
                    logger.error(f"Unexpected error during connection attempt: {e}")
                    self.connected = False
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying connection in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    return False
                        
        except Exception as e:
            logger.error(f"Error connecting to Minima indexer: {e}")
            self.connected = False
            return False
    
    async def call_tool(self, name, arguments):
        """
        Call a tool on the Minima indexer.
        
        Args:
            name: Name of the tool
            arguments: Arguments for the tool
        
        Returns:
            dict: Response from the tool
        """
        if not self.connected and not await self.connect():
            return {"error": "Could not connect to Minima indexer"}
        
        if name not in self.tools:
            return {"error": f"Tool {name} not found"}
            
        if name != "query":
            return {"error": "Unsupported tool"}
            
        # Extract the search query
        query_text = ""
        if isinstance(arguments, dict):
            query_text = arguments.get("text") or arguments.get("query", "")
        elif isinstance(arguments, str):
            query_text = arguments
        
        if not query_text:
            return {"error": "No search text provided"}
        
        logger.debug(f"Sending query to Minima: '{query_text}'")
        
        # Call the query API with retry logic
        max_retries = 3
        retry_delay = 2
        timeout = 90
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.server_url}/query",
                        json={"query": query_text},
                        timeout=timeout
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Error calling query API: {response.status}, {error_text}")
                            if response.status in [404, 503, 502, 500]:
                                self.connected = False
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                continue
                            return {"error": f"Error calling query API: {error_text}"}
                        
                        try:
                            result = await response.json()
                        except json.JSONDecodeError:
                            return {"error": "Invalid JSON response from server"}
                        
                        # Handle empty search results
                        if (isinstance(result, dict) and "result" in result and "output" in result["result"] and 
                            not result["result"].get("links") and not result["result"].get("sources")):
                            return {
                                "result": "No relevant documents found for this query. Please try a different search term.",
                                "sources": [],
                                "no_results": True
                            }
                        
                        # Process the result
                        if isinstance(result, dict):
                            if "result" in result and "output" in result["result"]:
                                output = result["result"]["output"]
                                sources = result["result"].get("links", [])
                            elif "output" in result:
                                output = result["output"]
                                sources = result.get("links", [])
                            else:
                                return {"result": result}
                            
                            # Verify sources
                            verified_sources = [s for s in sources if s and isinstance(s, str)]
                            if len(verified_sources) < len(sources):
                                logger.warning(f"Some sources could not be verified: {set(sources) - set(verified_sources)}")
                            
                            return self._format_result_with_citations(output, verified_sources)
                        
                        return {"result": result}
                        
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as e:
                logger.error(f"Connection error when calling query API: {e}")
                self.connected = False
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return {"error": f"Connection error: {str(e)}"}
                
        return {"error": "Query request failed after multiple attempts"}

    def _format_result_with_citations(self, output, sources):
        """
        Format the result with citations and source information.
        Returns a structured dictionary with content and processed citation details.
        
        Args:
            output: The output from Minima
            sources: List of verified sources
            
        Returns:
            dict: Structured result with 'retrieved_content', 'citations', and 'raw_source_paths'
        """
        logger.debug(f"[MINIMA_ADAPTER_TRACE] Initializing _format_result_with_citations. Output snippet: '{output[:200]}...', All raw sources from Minima: {sources}")

        if not sources:
            logger.warning("[MINIMA_ADAPTER_TRACE] No sources provided by Minima. Returning empty citations.")
            return {
                "retrieved_content": output + "\n\n⚠️ WARNING: No sources were cited by the search tool. This is a critical error if information was retrieved.",
                "citations": [],
                "raw_source_paths": []
            }
            
        processed_citations_details_list = [] 
        
        for source_index, source in enumerate(sources):
            if not source or not isinstance(source, str):
                logger.warning(f"[MINIMA_ADAPTER_TRACE] Source at index {source_index} is invalid or empty: '{source}'. Skipping.")
                continue
                
            logger.debug(f"[MINIMA_ADAPTER_TRACE] Processing source #{source_index}: '{source}'")
            source_lower = source.lower() 
            
            citation_text = ""
            applied_rule = "none"
            
            if "handbook" in source_lower:
                path_segment = source.split("handbook/", 1)[-1] if "handbook/" in source_lower else source
                path_segment = path_segment.replace(".md", "")
                citation_text = f"[Source: handbook.hypha.coop/{path_segment}]"
                applied_rule = "handbook"
                logger.debug(f"[MINIMA_ADAPTER_TRACE] Source '{source}' matched HANDBOOK rule. Formatted as: {citation_text}")
            elif "Hypha_PUBLIC_Drive" in source: 
                path_segment = source.split("Hypha_PUBLIC_Drive/", 1)[-1] if "Hypha_PUBLIC_Drive/" in source else source
                citation_text = f"[From Hypha's Public Drive: {path_segment}]"
                applied_rule = "hypha_public_drive"
                logger.debug(f"[MINIMA_ADAPTER_TRACE] Source '{source}' matched HYPHA_PUBLIC_DRIVE rule. Formatted as: {citation_text}")
            else:
                citation_text = f"[Source: {source}]"
                applied_rule = "generic"
                logger.debug(f"[MINIMA_ADAPTER_TRACE] Source '{source}' matched GENERIC rule. Formatted as: {citation_text}")
            
            processed_citations_details_list.append({"original_source": source, "formatted_citation": citation_text, "rule_applied": applied_rule})
        
        logger.debug(f"[MINIMA_ADAPTER_TRACE] All processed citation details (before unique): {processed_citations_details_list}")

        # Ensure unique citations based on the formatted_citation string, preserving order of first appearance
        unique_formatted_citations_seen = set()
        unique_processed_citations_details = []
        for detail in processed_citations_details_list:
            if detail["formatted_citation"] not in unique_formatted_citations_seen:
                unique_processed_citations_details.append(detail)
                unique_formatted_citations_seen.add(detail["formatted_citation"])
        
        # Sort unique citations by the 'formatted_citation' string for consistent ordering if needed,
        # or maintain first-seen order (current implementation above does first-seen).
        # For consistency similar to previous behavior, let's sort:
        unique_processed_citations_details = sorted(unique_processed_citations_details, key=lambda x: x["formatted_citation"])

        logger.debug(f"[MINIMA_ADAPTER_TRACE] Unique processed citation details: {unique_processed_citations_details}")
        
        final_result = {
            "retrieved_content": output,
            "citations": unique_processed_citations_details,
            "raw_source_paths": sources 
        }
        
        if not unique_processed_citations_details and sources: # Sources existed but none were valid/could be formatted
             logger.warning(f"[MINIMA_ADAPTER_TRACE] No valid citations could be generated from sources: {sources}. Adding warning to content.")
             final_result["retrieved_content"] = output + "\n\n⚠️ WARNING: Although sources were provided, none could be validly formatted. Please check source data integrity."


        logger.debug(f"[MINIMA_ADAPTER_TRACE] Final structured result: {final_result}")
        return final_result
    
    async def list_tools(self):
        return [
            {
                "name": name,
                "description": meta.get("description", ""),
                "parameters": meta.get("parameters", {}),
                "emoji": meta.get("emoji")
            }
            for name, meta in self.tools.items()
        ]

    def is_connected(self):
        """Check if connected to the Minima indexer."""
        return self.connected
        
    async def close(self):
        """Close the connection to the Minima indexer."""
        self.connected = False
        logger.info("Closed Minima REST adapter connection") 