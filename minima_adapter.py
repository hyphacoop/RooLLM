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
        
        # System prompt to encourage source citation
        self.citation_prompt = (
            "CRITICAL INSTRUCTION: You MUST cite your sources for EVERY piece of information retrieved from documents. "
            "For each statement or fact, include a specific citation to the source document. "
            "Use the format [Source: handbook.hypha.coop/path/to/document] IMMEDIATELY after each statement or claim. "
            "Failing to cite sources is a SERIOUS ERROR that affects reliability and trustworthiness. "
            "Users DEPEND on proper attribution and verification.\n\n"
            "Only cite documents that were returned by the query tool. "
            "If you don't have information from the documents, say so.\n\n"
            "Use the document content to answer questions and cite sources properly."
        )
        
        # Define available tools
        self.tools = {
            "query": {
                "name": "query",
                "description": "Find information in local files (PDF, CSV, DOCX, MD, TXT) and ALWAYS cite sources. You MUST include a citation for EVERY piece of information using the format [Source: handbook.hypha.coop/path/to/document]. Failing to cite sources is a critical error.",
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
            logger.info(f"Attempting to connect to Minima at {self.server_url}")
            test_payload = {"query": "test"}
            
            # Make sure the server URL has the correct format
            server_url = self.server_url
            if not server_url.startswith(("http://", "https://")):
                server_url = f"http://{server_url}"
                
            # Ensure the server URL doesn't end with a slash
            server_url = server_url.rstrip('/')
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        f"{server_url}/query", 
                        json=test_payload,
                        timeout=10  # Add a timeout to avoid hanging
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Successfully connected to Minima indexer at {server_url}")
                            
                            # Update the server URL if it was corrected
                            self.server_url = server_url
                            self.connected = True
                            return True
                        else:
                            logger.error(f"Failed to connect to Minima indexer: {response.status}")
                            error_text = await response.text()
                            logger.error(f"Error response: {error_text}")
                            self.connected = False
                            return False
                except aiohttp.ClientConnectorError as e:
                    logger.error(f"Could not connect to Minima server: {e}")
                    self.connected = False
                    return False
                except asyncio.TimeoutError:
                    logger.error("Connection to Minima server timed out")
                    self.connected = False
                    return False
                        
        except Exception as e:
            logger.error(f"Error connecting to Minima indexer: {e}")
            self.connected = False
            return False
    
    def get_tool_descriptions(self):
        """
        Get descriptions of available tools in a format compatible with LLM.
        
        Returns:
            list: Tool descriptions in a format compatible with LLM tools API
        """
        tool_descriptions = []
        
        for name, tool in self.tools.items():
            tool_desc = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            }
            tool_descriptions.append(tool_desc)
        
        return tool_descriptions
    
    async def call_tool(self, name, arguments):
        """
        Call a tool on the Minima indexer.
        
        Args:
            name: Name of the tool
            arguments: Arguments for the tool
        
        Returns:
            dict: Response from the tool
        """
        # Try to connect if not connected
        if not self.connected:
            success = await self.connect()
            if not success:
                return {"error": "Could not connect to Minima indexer"}
        
        if name not in self.tools:
            logger.error(f"Tool {name} not found")
            return {"error": f"Tool {name} not found"}
            
        try:
            if name == "query":
                # Extract the search query
                query_text = ""
                if isinstance(arguments, dict):
                    # Support both 'text' (our defined parameter) and 'query' (for compatibility with search_handbook)
                    if "text" in arguments:
                        query_text = arguments["text"]
                    elif "query" in arguments:
                        query_text = arguments["query"]
                elif isinstance(arguments, str):
                    query_text = arguments
                
                if not query_text:
                    return {"error": "No search text provided"}
                
                # Log the query being sent to Minima
                logger.info(f"Sending query to Minima: '{query_text}'")
                
                # Call the query API with retry logic
                max_retries = 3
                retry_delay = 2  # seconds
                timeout = 90  # increased timeout to 90 seconds
                
                for attempt in range(max_retries):
                    try:
                        async with aiohttp.ClientSession() as session:
                            url = f"{self.server_url}/query"
                            payload = {"query": query_text}
                            
                            logger.info(f"Searching for: {query_text} (attempt {attempt + 1}/{max_retries})")
                            
                            async with session.post(
                                url, 
                                json=payload,
                                timeout=timeout
                            ) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    logger.error(f"Error calling query API: {response.status}, {error_text}")
                                    # If we get a 404 or connection error, mark as disconnected
                                    if response.status in [404, 503, 502, 500]:
                                        self.connected = False
                                    return {"error": f"Error calling query API: {error_text}"}
                                
                                # Parse the response
                                try:
                                    result = await response.json()
                                    # Log the raw response from Minima
                                    logger.info(f"Raw Minima response: {json.dumps(result)[:500]}...")
                                except json.JSONDecodeError:
                                    raw_text = await response.text()
                                    logger.error(f"Failed to parse JSON response: {raw_text[:1000]}")
                                    return {"error": "Invalid JSON response from server"}
                                
                                # Handle empty search results
                                if (isinstance(result, dict) and "result" in result and "output" in result["result"] and 
                                    not result["result"].get("links") and not result["result"].get("sources")):
                                    logger.warning(f"No documents found for query: '{query_text}'")
                                    return {
                                        "result": "No relevant documents found for this query. Please try a different search term.",
                                        "sources": [],
                                        "no_results": True
                                    }
                                
                                # Check if the result contains the expected structure
                                if isinstance(result, dict) and "result" in result and "output" in result["result"]:
                                    # Format the result in a more readable way with citation prompt
                                    output = result["result"]["output"]
                                    sources = result["result"].get("links", [])
                                    
                                    # Verify sources exist
                                    verified_sources = self._verify_sources(sources)
                                    if len(verified_sources) < len(sources):
                                        logger.warning(f"Some sources could not be verified: {set(sources) - set(verified_sources)}")
                                    
                                    # Add citations instruction and format sources if available
                                    enhanced_result = self._format_result_with_citations(output, verified_sources)
                                    
                                    # Log the enhanced result that will be returned to RooLLM
                                    logger.info(f"Enhanced result for RooLLM: {json.dumps(enhanced_result)[:500]}...")
                                    
                                    return enhanced_result
                                elif isinstance(result, dict) and "output" in result:
                                    # Alternative format that might be used
                                    output = result["output"]
                                    sources = result.get("links", [])
                                    
                                    # Verify sources exist
                                    verified_sources = self._verify_sources(sources)
                                    if len(verified_sources) < len(sources):
                                        logger.warning(f"Some sources could not be verified: {set(sources) - set(verified_sources)}")
                                    
                                    # Add citations instruction and format sources if available
                                    enhanced_result = self._format_result_with_citations(output, verified_sources)
                                    
                                    # Log the enhanced result that will be returned to RooLLM
                                    logger.info(f"Enhanced result for RooLLM: {json.dumps(enhanced_result)[:500]}...")
                                    
                                    return enhanced_result
                                
                                # Just return whatever we got
                                logger.warning(f"Unexpected Minima response format: {json.dumps(result)[:500]}...")
                                return {"result": result}
                    except aiohttp.ClientConnectorError as e:
                        logger.error(f"Connection error when calling query API: {e}")
                        self.connected = False
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        return {"error": f"Connection error: {str(e)}"}
                    except asyncio.TimeoutError:
                        logger.error(f"Query request timed out (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        return {"error": "Query request timed out after multiple attempts"}
                
            return {"error": "Unsupported tool"}
                
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return {"error": f"Error calling tool: {str(e)}"}

    def _clean_source_path(self, path):
        """
        Clean and standardize a source path.
        
        Args:
            path: The source path to clean
            
        Returns:
            str: Cleaned source path
        """
        if not path or not isinstance(path, str):
            return path
            
        # Clean up the source path for consistency
        path = path.strip()
        
        # Remove .md extension if present
        if path.endswith('.md'):
            path = path[:-3]
            
        # Extract path after md_db/ and append to handbook.hypha.coop
        if 'md_db/' in path:
            path_parts = path.split('md_db/')
            if len(path_parts) > 1:
                path = f"handbook.hypha.coop/{path_parts[1]}"
                
        return path

    def _verify_sources(self, sources):
        """
        Verify that sources exist and are valid.
        
        Args:
            sources: List of source paths
            
        Returns:
            list: List of verified sources
        """
        verified_sources = []
        
        for source in sources:
            # For now, we just check if the source is a non-empty string
            if source and isinstance(source, str):
                # Clean up the source path using centralized method
                cleaned_source = self._clean_source_path(source)
                verified_sources.append(cleaned_source)
                logger.info(f"Verified source: {cleaned_source}")
            else:
                logger.warning(f"Invalid source: {source}")
        
        return verified_sources

    def is_connected(self):
        """Check if connected to the Minima indexer."""
        return self.connected
        
    async def close(self):
        """Close the connection to the Minima indexer."""
        # No need to close anything for REST API
        self.connected = False
        logger.info("Closed Minima REST adapter connection")

    def _format_result_with_citations(self, output, sources):
        """
        Format the result with citations and source information.
        
        Args:
            output: The output from Minima
            sources: List of verified sources
            
        Returns:
            dict: Formatted result with citations
        """
        # Clean and transform source paths using centralized method
        cleaned_sources = [self._clean_source_path(source) for source in sources]
            
        # Format the result with just the content and sources
        return {
            "result": output,
            "source_paths": cleaned_sources
        }
    
    async def list_tools(self):
        return [
            {
                "name": name,
                "description": meta.get("description", ""),
                "parameters": meta.get("parameters", {})
            }
            for name, meta in self.tools.items()
        ]

    def verify_citations(self, response_content, source_paths):
        """
        Verify that citations in the response match actual sources.
        
        Args:
            response_content: The model's response text
            source_paths: List of valid source paths
            
        Returns:
            tuple: (verified_response, needs_retry)
        """
        if not source_paths:
            return response_content, False
            
        # Check for citations in the format [Source: path] or [Source: number]
        citation_pattern = r'\[Source:\s*([^\]]+)\]'
        citations = re.findall(citation_pattern, response_content)
        
        if not citations:
            # No citations found, add a warning
            warning = "\n\n⚠️ WARNING: No sources were cited. Please cite your sources using the format [Source: handbook.hypha.coop/path/to/document]"
            return response_content + warning, True
            
        # Verify each citation
        invalid_citations = []
        for citation in citations:
            # Check if it's a number citation
            if citation.strip().isdigit():
                num = int(citation.strip())
                if 1 <= num <= len(source_paths):
                    # Replace number with actual path, ensuring it's cleaned
                    actual_path = self._clean_source_path(source_paths[num-1])
                    response_content = response_content.replace(f"[Source: {citation}]", f"[Source: {actual_path}]")
                else:
                    invalid_citations.append(citation)
            # Check if it's a path citation
            elif not any(citation.strip() == path for path in source_paths):
                invalid_citations.append(citation)
                
        if invalid_citations:
            warning = f"\n\n⚠️ WARNING: The following citations are invalid: {', '.join(invalid_citations)}. Please use only the exact source paths provided."
            return response_content + warning, True
            
        return response_content, False 