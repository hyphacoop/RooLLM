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

        # Check if metadata tools are enabled (from config, set via branding.json)
        config_metadata = config.get("USE_MINIMA_METADATA") if config else None
        self.metadata_enabled = bool(config_metadata) if config_metadata is not None else False
        
        self.connected = False
        self.tools = {}
        self.last_connection_attempt = 0
        self.connection_retry_interval = 10  # seconds
        
        # Define available tools
        self.tools = {
            "query": {
                "name": "query",
                "description": "Primary tool for searching the knowledge base. Use this first for questions about documents, topics, file contents, or anything that may be answered from indexed files. Results include content plus source metadata such as filename, description, and tags. Preserves inline [Source: path] citations.",
                "emoji": "🗃️",
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
            },
        }

        if self.metadata_enabled:
            self.tools.update({
                "get_file_metadata": {
                    "name": "get_file_metadata",
                    "description": "Use only when the user explicitly asks for description/tags/metadata for a specific file, or after query has identified a relevant file and the user asks about that file's metadata. Use path when known, or filename when only the basename is known.",
                    "emoji": "🧾",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Optional file path, such as /documents/foo.pdf or a path under the Minima file root"
                            },
                            "filename": {
                                "type": "string",
                                "description": "Optional file basename, such as foo.pdf, when the full path is unknown"
                            }
                        }
                    }
                },
                "update_file_metadata": {
                    "name": "update_file_metadata",
                    "description": "Use only when the user explicitly asks to change a file's description or tags. Use path when known, or filename when only the basename is known.",
                    "emoji": "🖊️",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Optional file path, such as /documents/foo.pdf or a path under the Minima file root"
                            },
                            "filename": {
                                "type": "string",
                                "description": "Optional file basename, such as foo.pdf, when the full path is unknown"
                            },
                            "description": {
                                "type": "string",
                                "description": "Human-readable file description"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "File tags"
                            }
                        }
                    }
                },
                "list_file_metadata": {
                    "name": "list_file_metadata",
                    "description": "Use only when the user asks to list or browse files or metadata records. Returns all files known to Minima with description, tags, filename, relative path, and path.",
                    "emoji": "🗂️",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                },
            })
        
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
            # Prefer non-query probes to avoid generating synthetic query traffic
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
                            # 1) OpenAPI endpoint used by current minima indexer deployment
                            async with session.get(
                                f"{server_url}/indexer/openapi.json",
                                timeout=connection_timeout
                            ) as openapi_response:
                                if openapi_response.status == 200:
                                    try:
                                        openapi = await openapi_response.json()
                                        paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
                                        if "/query" in paths:
                                            logger.debug(
                                                f"Successfully connected to Minima indexer at {server_url} "
                                                f"via /indexer/openapi.json"
                                            )
                                            self.server_url = server_url
                                            self.connected = True
                                            return True
                                    except Exception:
                                        # Keep probing other known shapes.
                                        pass

                            # 2) Generic OpenAPI fallback
                            async with session.get(f"{server_url}/openapi.json", timeout=connection_timeout) as openapi_response:
                                if openapi_response.status == 200:
                                    try:
                                        openapi = await openapi_response.json()
                                        paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
                                        if "/query" in paths:
                                            logger.debug(
                                                f"Successfully connected to Minima indexer at {server_url} "
                                                f"via /openapi.json"
                                            )
                                            self.server_url = server_url
                                            self.connected = True
                                            return True
                                    except Exception:
                                        pass

                            # 3) Health endpoint (if available)
                            async with session.get(f"{server_url}/health", timeout=connection_timeout) as health_response:
                                if health_response.status == 200:
                                    logger.debug(f"Successfully connected to Minima indexer at {server_url} via /health")
                                    self.server_url = server_url
                                    self.connected = True
                                    return True

                            # 4) Status endpoint (newer indexer variants)
                            async with session.get(f"{server_url}/status", timeout=connection_timeout) as status_response:
                                if status_response.status == 200:
                                    logger.debug(f"Successfully connected to Minima indexer at {server_url} via /status")
                                    self.server_url = server_url
                                    self.connected = True
                                    return True

                            # 5) Last resort: POST /query for backward compatibility
                            async with session.post(
                                f"{server_url}/query",
                                json=test_payload,
                                timeout=connection_timeout
                            ) as response:
                                if response.status == 200:
                                    logger.debug(f"Successfully connected to Minima indexer at {server_url} via /query")

                                    # Update the server URL if it was corrected
                                    self.server_url = server_url
                                    self.connected = True
                                    return True

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

        if name == "get_file_metadata":
            arguments = arguments if isinstance(arguments, dict) else {}
            path = arguments.get("path")
            filename = arguments.get("filename")
            if not path and not filename:
                return {"error": "path or filename is required"}
            return await self.get_metadata(path=path, filename=filename)

        if name == "update_file_metadata":
            arguments = arguments if isinstance(arguments, dict) else {}
            path = arguments.get("path")
            filename = arguments.get("filename")
            if not path and not filename:
                return {"error": "path or filename is required"}
            return await self.put_metadata(
                path=path,
                filename=filename,
                description=arguments.get("description", ""),
                tags=arguments.get("tags", []),
            )

        if name == "list_file_metadata":
            return await self.list_metadata()

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
                                chunks = result["result"].get("chunks", [])
                            elif "output" in result:
                                output = result["output"]
                                sources = result.get("links", [])
                                chunks = result.get("chunks", [])
                            else:
                                return {"result": result}

                            # Verify sources
                            verified_sources = [s for s in sources if s and isinstance(s, str)]
                            if len(verified_sources) < len(sources):
                                logger.warning(f"Some sources could not be verified: {set(sources) - set(verified_sources)}")

                            # Use chunk-level citations if available
                            if chunks:
                                return self._format_result_with_chunk_citations(chunks)
                            else:
                                # Fallback to old format
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

    async def get_metadata(self, path=None, filename=None):
        if not self.connected and not await self.connect():
            return {"error": "Could not connect to Minima indexer"}

        endpoint = "metadata/by-filename" if filename and not path else "metadata"
        params = {"filename": filename} if endpoint.endswith("by-filename") else {"path": path}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.server_url}/{endpoint}",
                params=params,
                timeout=30,
            ) as response:
                try:
                    payload = await response.json()
                except json.JSONDecodeError:
                    payload = {"error": await response.text()}
                if response.status != 200:
                    return {"error": payload.get("detail") or payload.get("error") or "Metadata request failed"}
                return payload

    async def put_metadata(self, path=None, description="", tags=None, filename=None):
        if not self.connected and not await self.connect():
            return {"error": "Could not connect to Minima indexer"}

        payload = {"description": description, "tags": tags or []}
        if path:
            payload["path"] = path
        if filename:
            payload["filename"] = filename
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.server_url}/metadata",
                json=payload,
                timeout=30,
            ) as response:
                try:
                    payload = await response.json()
                except json.JSONDecodeError:
                    payload = {"error": await response.text()}
                if response.status != 200:
                    return {"error": payload.get("detail") or payload.get("error") or "Metadata update failed"}
                return payload

    async def list_metadata(self):
        if not self.connected and not await self.connect():
            return {"error": "Could not connect to Minima indexer"}

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.server_url}/metadata/list", timeout=30) as response:
                try:
                    payload = await response.json()
                except json.JSONDecodeError:
                    payload = {"error": await response.text()}
                if response.status != 200:
                    return {"error": payload.get("detail") or payload.get("error") or "Metadata list request failed"}
                return payload

    def _format_result_with_chunk_citations(self, chunks):
        """
        Format the result with chunk-level citations where each snippet is paired with its source.

        Args:
            chunks: List of dicts with 'content' and 'source' keys

        Returns:
            dict: Formatted result with inline citations
        """
        logger.debug(f"Formatting result with {len(chunks)} chunks")

        if not chunks:
            logger.warning("No chunks provided for result formatting.")
            return {
                "result": "⚠️ WARNING: No content was retrieved from the search tool.",
                "source_paths": []
            }

        formatted_output = []
        all_sources = []

        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, dict) or 'content' not in chunk or 'source' not in chunk:
                logger.warning(f"Invalid chunk format at index {i}: {chunk}")
                continue

            content = chunk['content']
            source = chunk['source']

            if not source or not isinstance(source, str):
                logger.warning(f"Invalid source in chunk {i}: {source}")
                continue

            all_sources.append(source)

            # Format the source citation
            citation_text = f"[Source: {source}]"

            # Add the content followed immediately by its citation
            formatted_output.append(f"{content} {citation_text}")
            logger.debug(f"Chunk {i}: paired content with citation {citation_text}")

        if not formatted_output:
            logger.warning("No valid chunks could be formatted.")
            return {
                "result": "⚠️ WARNING: Although chunks were provided, none could be validly formatted.",
                "source_paths": []
            }

        # Join all chunks with a separator
        final_output = "\n\n".join(formatted_output)

        logger.debug(f"Final output length: {len(final_output)} characters")

        return {
            "result": final_output,
            "source_paths": all_sources
        }

    def _format_result_with_citations(self, output, sources):
        """
        Format the result with citations and source information.
        Aims to cite all sources provided by Minima, with special formatting for known paths.
        
        Args:
            output: The output from Minima
            sources: List of verified sources
            
        Returns:
            dict: Formatted result with citations
        """
        logger.debug(f"Formatting result. Initial output snippet: '{output[:200]}...', All sources: {sources}")

        if not sources:
            logger.warning("No sources provided by Minima for result formatting.")
            return {
                "result": output + "\n\n⚠️ WARNING: No sources were cited by the search tool. This is a critical error if information was retrieved.",
                "source_paths": []
            }
            
        formatted_citations = []
        
        for source in sources:
            if not source or not isinstance(source, str):
                logger.warning(f"Invalid or empty source found in sources list: {source}. Skipping this source.")
                continue
                
            logger.debug(f"Processing source for citation: '{source}'")
            citation_text = f"[Source: {source}]"
            logger.debug(f"Formatted source citation: {citation_text}")
            
            formatted_citations.append(citation_text)
        
        if formatted_citations:
            # Remove duplicates by converting to set and back to list, then sort for consistent order
            unique_sorted_citations = sorted(list(set(formatted_citations)))
            output += "\n\n" + "\n".join(unique_sorted_citations)
            logger.debug(f"Appended citations to output. Final output snippet with citations: '{output[:300]}...'")
        else:
            # This case should now only be hit if all source strings were empty or invalid,
            # which is handled by the 'continue' in the loop.
            # If `sources` was non-empty but all were invalid, formatted_citations would be empty.
            logger.warning("No valid sources could be formatted from the provided list. Original sources: {sources}")
            output += "\n\n⚠️ WARNING: Although sources were provided, none could be validly formatted. Please check source data integrity."
        
        return {
            "result": output,
            "source_paths": sources # Always return the original, complete list of sources from Minima
        }
    
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
