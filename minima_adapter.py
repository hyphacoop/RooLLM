import logging
import json
import os
import aiohttp
from dotenv import load_dotenv
import asyncio
import time

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
        self.using_minima = (
            config.get("USE_MINIMA_MCP") if config else None
        ) or os.getenv("USE_MINIMA_MCP", "false").lower() == "true"
        
        self.connected = False
        self.tools = {}
        self.last_connection_attempt = 0
        self.connection_retry_interval = 10  # seconds
        
        # System prompt to encourage source citation
        self.citation_prompt = (
            "CRITICAL INSTRUCTION: You MUST cite your sources for EVERY piece of information retrieved from documents. "
            "For each statement or fact, include a specific citation to the source document. "
            "Use the format [Source: document_name] IMMEDIATELY after each statement or claim. "
            "Failing to cite sources is a SERIOUS ERROR that affects reliability and trustworthiness. "
            "Users DEPEND on proper attribution and verification."
        )
        
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
                            
                            # Define available tools
                            self.tools = {
                                "query": {
                                    "name": "query",
                                    "description": "Find information in local files (PDF, CSV, DOCX, MD, TXT) and ALWAYS cite sources. You MUST include a citation for EVERY piece of information using the format [Source: document_name]. Failing to cite sources is a critical error.",
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
                
                # Call the query API
                async with aiohttp.ClientSession() as session:
                    url = f"{self.server_url}/query"
                    payload = {"query": query_text}
                    
                    logger.info(f"Searching for: {query_text}")
                    
                    try:
                        async with session.post(
                            url, 
                            json=payload,
                            timeout=45  # Allow more time for search
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
                        return {"error": f"Connection error: {str(e)}"}
                    except asyncio.TimeoutError:
                        logger.error("Query request timed out")
                        return {"error": "Query request timed out"}
                
            return {"error": "Unsupported tool"}
                
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return {"error": f"Error calling tool: {str(e)}"}

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
                # Clean up the source path for consistency
                source = source.strip()
                verified_sources.append(source)
                logger.info(f"Verified source: {source}")
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
        Format the result with citation instructions and source information.
        
        Args:
            output: The output text from Minima
            sources: List of source links/documents
            
        Returns:
            dict: Enhanced result with source citations
        """
        # If no sources, just return the original output with a note
        if not sources or len(sources) == 0:
            return {
                "result": output + "\n\nNo document sources were found for this query.",
                "sources": [],
                "citation_prompt": self.citation_prompt
            }
            
        # Format source information with full paths and structured context
        formatted_sources = []
        source_paths = []  # List of exact paths that can be cited
        
        for i, source in enumerate(sources):
            # Get full path for local reference
            full_path = source
            source_paths.append(full_path)  # Add to allowed citation paths
            
            # Get just the filename from the path/URL if possible
            if '/' in source:
                source_name = source.split('/')[-1]
                # For MD files, add the section name if available
                if source_name.endswith('.md') and '#' in source:
                    section = source.split('#')[-1].replace('-', ' ').title()
                    source_name = f"{source_name} (Section: {section})"
            else:
                source_name = source
                
            # Create formatted source string for display
            formatted_sources.append(f"[{i+1}] {source_name} - Full path: {full_path}")
        
        # Format the output with detailed citation info
        citation_header = "\n\n-------- DOCUMENT SOURCES --------"
        citations = f"{citation_header}\n" + "\n".join(formatted_sources)
        
        # Create a more explicit instruction with the exact list of allowed sources
        allowed_sources_formatted = []
        for i, source in enumerate(source_paths):
            allowed_sources_formatted.append(f"- [{i+1}] \"{source}\"")
            
        allowed_sources_list = "\n".join(allowed_sources_formatted)
        
        source_specific_instruction = (
            f"⚠️ CITATION REQUIREMENT ⚠️\n"
            f"You are ONLY allowed to cite the following specific documents:\n"
            f"{allowed_sources_list}\n\n"
            f"When citing, you MUST use the EXACT path as shown above - do not modify, abbreviate, or create new paths.\n"
            f"Format your citations as [Source: full/path/to/document] immediately after each claim or statement.\n"
            f"ANY citation not matching one of the exact sources above will be flagged as a hallucination.\n"
            f"If you cannot find relevant information in these sources, state clearly that you don't have information on that topic."
        )
        
        # Prepare a pre-formatted result with the document context first
        context_header = "DOCUMENT CONTEXT FOR YOUR RESPONSE:"
        context_and_output = (
            f"{context_header}\n\n"
            f"The following documents were found for this query. You must ONLY cite these exact documents:\n"
            f"{allowed_sources_list}\n\n"
            f"Document content:\n{output}"
        )
        
        # Enhanced result with citation prompt and formatted sources
        return {
            "result": context_and_output,
            "original_output": output,
            "sources": sources,
            "source_paths": source_paths,  # Include exact allowed paths for verification
            "formatted_sources": formatted_sources,
            "citations": citations,
            "citation_prompt": self.citation_prompt,
            "source_specific_instruction": source_specific_instruction
        } 