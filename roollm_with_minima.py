import json
import logging
import asyncio
import os
from dotenv import load_dotenv
import time
import re

# Use try-except pattern for imports that can work both in package mode and standalone mode
try:
    from .roollm import RooLLM, make_message, ROLE_TOOL, ROLE_SYSTEM, BASE_TOOL_LIST
    from .minima_adapter import MinimaRestAdapter
    from .system_messages import MINIMA_SYSTEM_MESSAGES, TOOL_SELECTION_GUIDE
except ImportError:
    from roollm import RooLLM, make_message, ROLE_TOOL, ROLE_SYSTEM, BASE_TOOL_LIST
    from minima_adapter import MinimaRestAdapter
    from system_messages import MINIMA_SYSTEM_MESSAGES, TOOL_SELECTION_GUIDE

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class RooLLMWithMinima(RooLLM):
    """
    Extended RooLLM class that uses a Minima indexer for document retrieval.
    
    This class extends the base RooLLM functionality by adding integration
    with a Minima indexer, allowing Claude to search and retrieve information
    from local documents while maintaining privacy.
    """
    
    def __init__(self, inference, tool_list=None, config=None):
        """
        Initialize RooLLMWithMinima.
        
        Args:
            inference: Inference function for the LLM
            tool_list: List of tools to load
            config: Configuration dictionary
        """
        # Initialize REST adapter for Minima with config
        self.minima_adapter = MinimaRestAdapter(config=config)
        self.minima_tools = []
        
        # Store the requested tool list
        self.requested_tool_list = tool_list
        
        # Track connection state
        self._minima_connection_attempted = False
        self._minima_connection_failed = False
        self._minima_last_attempt = 0
        self._minima_retry_interval = 300  # 5 minutes between retries
        
        # Call parent constructor with possibly modified tool list
        super().__init__(inference, tool_list, config)
        
        # Check if Minima integration is enabled
        if self.minima_adapter.using_minima:
            logger.info("Minima integration is enabled")
        else:
            logger.info("Minima integration is disabled")
    
    def _build_tool_list(self):
        """Build tool list based on available configurations, excluding search_handbook if Minima is enabled"""
        # Get the base tool list from parent
        if self.requested_tool_list is not None:
            tools = self.requested_tool_list.copy()
        else:
            tools = super()._build_tool_list()
            
        # If Minima is enabled, remove search_handbook from the tool list
        if self.minima_adapter.using_minima and "search_handbook" in tools:
            logger.info("Removing search_handbook tool as Minima is enabled")
            tools.remove("search_handbook")
            
        return tools
    
    async def connect_to_minima(self):
        """Connect to the Minima indexer and initialize tools."""
        if not self.minima_adapter.using_minima:
            logger.info("Minima integration is disabled, skipping connection")
            return False
            
        connected = await self.minima_adapter.connect()
        
        if connected:
            self.minima_tools = self.minima_adapter.get_tool_descriptions()
            logger.info(f"Connected to Minima indexer with {len(self.minima_tools)} tools")
            return True
        else:
            logger.warning("Failed to connect to Minima indexer")
            return False
    
    def _handle_minima_result(self, result, query):
        """
        Handle the result from Minima and format it for the model.
        
        Args:
            result: The result from Minima
            query: The original query
            
        Returns:
            str: Formatted result with citations
        """
        if not result or "error" in result:
            return "Error retrieving information from documents."
            
        # Get the formatted result with citations
        formatted_result = result.get("result", "")
        sources = result.get("sources", [])
        
        # Add citation instructions if sources are available
        if sources:
            citation_instructions = (
                "\n\n⚠️ CITATION REQUIREMENT ⚠️\n"
                "You MUST cite your sources using the EXACT paths provided below.\n"
                "Format: [Source: handbook.hypha.coop/path/to/document]\n"
                "Example: [Source: handbook.hypha.coop/Policies/pet]\n\n"
                "Available sources:\n"
            )
            
            # Add each source with its number
            for i, source in enumerate(sources, 1):
                clean_source = self._clean_path(source)
                citation_instructions += f"[{i}] {clean_source}\n"
                
            formatted_result += citation_instructions
            
        return formatted_result
        
    async def _process_with_minima(self, query, max_retries=3):
        """
        Process a query using Minima with retries for citation verification.
        
        Args:
            query: The query to process
            max_retries: Maximum number of retries for citation verification
            
        Returns:
            str: The processed response with verified citations
        """
        retries = 0
        while retries < max_retries:
            # Get result from Minima
            result = await self.minima_adapter.call_tool("query", {"text": query})
            
            # Format the result
            formatted_result = self._handle_minima_result(result, query)
            
            # Verify citations using the adapter's method
            if "source_paths" in result:
                verified_response, needs_retry = self.minima_adapter.verify_citations(formatted_result, result["source_paths"])
                
                if not needs_retry:
                    return verified_response
                    
                retries += 1
                if retries < max_retries:
                    # Add retry instruction
                    retry_instruction = "\n\nPlease try again with proper citations using the exact source paths provided."
                    formatted_result += retry_instruction
                    
        return verified_response

    def _extract_sources_from_result(self, result):
        """
        Extract and clean source paths from a Minima result.
        
        Args:
            result: The Minima result
            
        Returns:
            tuple: (sources, exact_paths)
        """
        sources = []
        exact_paths = []
        
        if 'sources' in result:
            for source in result['sources']:
                clean_source = self._clean_path(source)
                sources.append(clean_source)
                exact_paths.append(clean_source)
                
        if 'source_paths' in result:
            for path in result['source_paths']:
                clean_path = self._clean_path(path)
                if clean_path not in exact_paths:
                    exact_paths.append(clean_path)
                    
        elif 'structured_sources' in result:
            for source in result['structured_sources']:
                clean_path = self._clean_path(source['path'])
                sources.append(clean_path)
                exact_paths.append(clean_path)
                
        return sources, exact_paths

    def _build_system_messages(self):
        """
        Build system messages for Minima integration.
        
        Returns:
            list: List of system messages
        """
        messages = []
        
        if self.minima_adapter.using_minima and self.minima_adapter.is_connected():
            messages.extend(MINIMA_SYSTEM_MESSAGES)
            
        return messages

    async def _ensure_minima_connection(self):
        """
        Ensure Minima is connected, with proper error handling and retry logic.
        
        Returns:
            bool: True if connected, False if connection failed
        """
        if not self.minima_adapter.using_minima:
            return False
            
        # If we've already tried and failed to connect, don't try again unless retry interval has passed
        if self._minima_connection_failed:
            current_time = time.time()
            if current_time - self._minima_last_attempt < self._minima_retry_interval:
                return False
            # Reset failure state for retry
            self._minima_connection_failed = False
            
        # If we're already connected, return True
        if self.minima_adapter.is_connected():
            return True
            
        # If we haven't tried to connect yet, try now
        if not self._minima_connection_attempted:
            self._minima_connection_attempted = True
            self._minima_last_attempt = time.time()
            try:
                connected = await self.connect_to_minima()
                if not connected:
                    self._minima_connection_failed = True
                    logger.warning("Failed to connect to Minima indexer - will retry in 5 minutes")
                return connected
            except Exception as e:
                self._minima_connection_failed = True
                logger.error(f"Error connecting to Minima: {e}")
                return False
                
        return False

    def _clean_response_content(self, content):
        """
        Clean up response content by removing any unexpected artifacts.
        
        Args:
            content: The response content to clean
            
        Returns:
            str: Cleaned response content
        """
        if not content:
            return content
            
        # Remove any text after end_of_text marker
        if "<|end_of_text|>" in content:
            content = content.split("<|end_of_text|>")[0]
            
        # Remove any URLs or JSON artifacts
        content = re.sub(r'https?://\S+', '', content)
        content = re.sub(r'<\|begin_of_text\|>.*', '', content)
        
        return content.strip()

    async def chat(self, user, content, history=[], limit_tools=None, react_callback=None):
        """
        Enhanced chat method that incorporates Minima tools.
        
        This extends the base RooLLM chat method to include Minima tools
        in the set of available tools for the LLM.
        
        Args:
            user: User name
            content: User message content
            history: Chat history
            limit_tools: List of tools to limit to
            react_callback: Callback function for reactions
            
        Returns:
            dict: Response from the LLM
        """
        # Log user query
        logger.info(f"User query: {content}")
        
        # Try to connect to Minima if needed
        minima_connected = await self._ensure_minima_connection()
        
        # Prepare messages
        system_message = make_message(ROLE_SYSTEM, self.make_system())
        user_message = make_message("user", user + ': ' + content)
        messages = [system_message, *history, user_message]
        
        # Get tool descriptions from RooLLM
        tools = self.tools
        if limit_tools:
            tools = tools.subset(limit_tools)
        
        tool_descriptions = tools.descriptions()
        
        # Add Minima tools if connected
        if minima_connected:
            # Make all tools available to the LLM
            combined_tools = tool_descriptions + self.minima_tools
            logger.info(f"Using {len(tool_descriptions)} RooLLM tools and {len(self.minima_tools)} Minima tools")
            
            # Add a system message to guide tool selection
            tool_selection_guide = make_message(ROLE_SYSTEM, TOOL_SELECTION_GUIDE)
            messages.append(tool_selection_guide)
        else:
            if self.minima_adapter.using_minima:
                logger.info(f"Using {len(tool_descriptions)} RooLLM tools (Minima not connected)")
                # Add a message to inform the user that Minima is not available
                messages.append(make_message(ROLE_SYSTEM, 
                    "Note: Document search functionality is currently unavailable. "
                    "I'll do my best to answer your question using other available tools."
                ))
            else:
                logger.info(f"Using {len(tool_descriptions)} RooLLM tools (Minima not enabled)")
        
        # For tracking Minima usage and sources
        minima_sources_used = []
        minima_exact_paths = []
        minima_was_called = False
        minima_query_responses = []  # Track the responses from Minima
        
        # Send first request to the LLM
        response = await self.inference(messages, combined_tools)
        
        # Clean up response content
        if 'content' in response:
            response['content'] = self._clean_response_content(response['content'])
        
        # Handle tool calls in the response
        while 'tool_calls' in response:
            messages.append(response)
            
            for call in response["tool_calls"]:
                if not 'function' in call:
                    continue
                    
                func = call['function']
                tool_name = func['name']
                
                # Check if this is a Minima tool
                is_minima_tool = self.minima_adapter.using_minima and self.minima_adapter.is_connected() and tool_name in self.minima_adapter.tools
                
                # Track if Minima was used
                if is_minima_tool:
                    minima_was_called = True
                
                # Handle tool emoji
                tool_emoji = "🔍" if is_minima_tool else tools.get_tool_emoji(tool_name=tool_name)
                if tool_emoji and react_callback:
                    await react_callback(tool_emoji)
                    await asyncio.sleep(0.5)
                
                # Call the appropriate tool
                if is_minima_tool:
                    logger.info(f"Calling Minima tool: {tool_name}")
                    try:
                        # Parse arguments
                        arguments = (func['arguments'] if isinstance(func['arguments'], dict)
                                   else json.loads(func['arguments']))
                        
                        result = await self.minima_adapter.call_tool(tool_name, arguments)
                        
                        # Store query response
                        minima_query_responses.append({
                            "query": arguments,
                            "result": result
                        })
                        
                        # Extract and track sources
                        sources, exact_paths = self._extract_sources_from_result(result)
                        minima_sources_used.extend(sources)
                        minima_exact_paths.extend(exact_paths)
                        
                        # Process result and update messages
                        formatted_result = self._handle_minima_result(result, arguments.get("text", ""))
                        processed_result = {
                            "result": formatted_result,
                            "sources": sources,
                            "source_paths": exact_paths
                        }
                        
                    except Exception as e:
                        logger.error(f"Error executing Minima tool: {e}")
                        processed_result = {
                            "error": f"Failed to execute Minima query: {str(e)}"
                        }
                else:
                    logger.info(f"Calling RooLLM tool: {tool_name}")
                    # Ensure arguments is a valid dictionary
                    tool_args = {}
                    if func.get('arguments'):
                        try:
                            tool_args = (func['arguments'] if isinstance(func['arguments'], dict)
                                       else json.loads(func['arguments']))
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid arguments for tool {tool_name}, using empty dict")
                    processed_result = await tools.call(self, tool_name, tool_args, user)
                
                # Append tool result to messages
                messages.append(make_message(ROLE_TOOL, json.dumps(processed_result)))
            
            # Get next response from LLM
            response = await self.inference(messages, combined_tools)
        
        # Log the final response for comparison/debugging
        if 'content' in response:
            logger.info(f"Final model response (before verification): {response['content'][:500]}...")
        
        # If Minima was called, verify citations in the final response and log detailed comparison
        if minima_was_called and 'content' in response:
            self._log_minima_content_comparison(response['content'], minima_query_responses, minima_exact_paths or minima_sources_used)
            
            # Use exact paths for verification if available, otherwise fall back to sources
            verify_against = minima_exact_paths if minima_exact_paths else minima_sources_used
            verified_response, needs_retry = self._verify_citations_in_response(response, verify_against)
            if needs_retry:
                logger.warning("Citation verification failed, needs retry")
            response = verified_response
            
        return response
    
    def _log_minima_content_comparison(self, response_content, minima_responses, valid_sources):
        """
        Log detailed comparison between what Minima returned and what the model said.
        This helps identify potential hallucinations or misinterpretations.
        
        Args:
            response_content: The model's response content
            minima_responses: List of Minima query responses
            valid_sources: List of valid source paths
        """
        logger.info("=============== MINIMA CONTENT COMPARISON ===============")
        logger.info(f"Model used {len(minima_responses)} Minima queries and has {len(valid_sources)} valid sources")
        
        # Extract citations from content
        import re
        citation_pattern = r'\[Source: ([^\]]+)\]'
        cited_sources = re.findall(citation_pattern, response_content)
        
        logger.info(f"Model cited {len(cited_sources)} sources in its response")
        
        # Compare valid sources with cited sources
        cited_set = set(cited_sources)
        valid_set = set(valid_sources)
        
        # Check if any source was cited but not provided by Minima
        hallucinated = cited_set - valid_set
        if hallucinated:
            logger.warning(f"HALLUCINATION DETECTED: Model cited {len(hallucinated)} sources that were not provided by Minima")
            for source in hallucinated:
                logger.warning(f"  - Hallucinated source: {source}")
        
        # Log each Minima query and its response for comparison
        for idx, query_response in enumerate(minima_responses):
            query = query_response["query"]
            result = query_response["result"]
            
            logger.info(f"--- Minima Query #{idx+1} ---")
            if isinstance(query, dict):
                if "text" in query:
                    logger.info(f"Query: {query['text']}")
                elif "query" in query:
                    logger.info(f"Query: {query['query']}")
            else:
                logger.info(f"Query: {query}")
                
            # Log sources provided by Minima
            if "sources" in result:
                logger.info(f"Sources provided by Minima: {result['sources']}")
            elif "structured_sources" in result:
                logger.info(f"Structured sources provided by Minima: {[s['path'] for s in result['structured_sources']]}")
                
            # Log actual content provided by Minima
            if "result" in result:
                content = result["result"]
                logger.info(f"Minima result content: {content[:300]}...")
                
        logger.info("========================================================")
    
    def _clean_path(self, path):
        """
        Centralized method to clean and normalize paths.
        Removes .md extensions, spaces, and normalizes to handbook.hypha.coop format.
        
        Args:
            path: The path to clean
            
        Returns:
            str: Cleaned and normalized path
        """
        if not path or not isinstance(path, str):
            return path
            
        # Clean the path first
        clean_path = path.strip()
        
        # Handle file:// paths
        if clean_path.startswith('file://'):
            clean_path = clean_path.replace('file://', '')
            
        # Remove .md extension if present (anywhere in the path)
        clean_path = clean_path.replace('.md', '')
            
        # Remove spaces
        clean_path = clean_path.replace(' ', '')
        
        # Normalize slashes
        clean_path = clean_path.replace('//', '/')
        
        # Convert to handbook.hypha.coop format if it's a local path
        if 'md_db/' in clean_path:
            path_parts = clean_path.split('md_db/')
            if len(path_parts) > 1:
                clean_path = f"handbook.hypha.coop/{path_parts[1]}"
                
        return clean_path

    def _transform_source_path(self, source_path):
        """
        Transform a source path to the handbook.hypha.coop format.
        
        Args:
            source_path: The original source path
            
        Returns:
            str: Transformed path in handbook.hypha.coop format
        """
        return self._clean_path(source_path)

    def _extract_citations(self, content):
        """
        Extract citations from content using multiple patterns.
        
        Args:
            content: The content to search for citations
            
        Returns:
            list: List of extracted citations
        """
        import re
        citation_patterns = [
            r'\[Source: ([^\]]+)\]',  # Standard format
            r'Source: \[([^\]]+)\]',  # Alternative format
            r'Source:\s*\[([^\]]+)\]',  # With optional whitespace
            r'\[(\d+)\]:',  # Numbered citation format
            r'Source: \[(\d+)\]'  # Numbered source format
        ]
        
        citations = []
        for pattern in citation_patterns:
            citations.extend(re.findall(pattern, content))
            
        # Clean up citations using the centralized path cleaning method
        return [self._clean_path(citation) for citation in citations]

    def _find_closest_match(self, citation, valid_sources):
        """
        Find the closest matching source for a citation.
        
        Args:
            citation: The citation to match
            valid_sources: List of valid source paths
            
        Returns:
            str or None: Closest matching source or None if no match found
        """
        # Clean the citation using the centralized method
        clean_citation = self._clean_path(citation)
            
        # First try exact match
        if clean_citation in valid_sources:
            return clean_citation
            
        # Handle numbered citations
        if clean_citation.isdigit():
            try:
                index = int(clean_citation) - 1
                if 0 <= index < len(valid_sources):
                    return valid_sources[index]
            except (ValueError, IndexError):
                pass
            
        # Then try partial matches
        for source in valid_sources:
            clean_source = self._clean_path(source)
            if clean_citation in clean_source or clean_source in clean_citation:
                return source
                
        return None

    def _create_warning_message(self, warning_type, details=None):
        """
        Create standardized warning messages.
        
        Args:
            warning_type: Type of warning ('no_citations' or 'hallucinated_sources')
            details: Additional details for the warning (e.g., list of hallucinated sources)
            
        Returns:
            str: Formatted warning message
        """
        if warning_type == 'no_citations':
            return (
                "\n\n⚠️ **Warning**: No citations were included in this response, "
                "despite information potentially coming from documents. "
                "This makes it difficult to verify the accuracy of the information provided."
            )
        elif warning_type == 'hallucinated_sources' and details:
            warning_message = (
                "\n\n⚠️ **WARNING: HALLUCINATED SOURCES DETECTED** ⚠️\n"
                "The following citations do not match any of the actual document sources:\n"
            )
            warning_message += "\n".join(f"- ❌ [{source}]" for source in details)
            warning_message += (
                "\n\nThe information attributed to these non-existent sources may be inaccurate or fabricated. "
                "Please disregard these claims or verify them through other means."
            )
            return warning_message
        return ""

    def _verify_citations_in_response(self, response, minima_result):
        """
        Verify that citations in the response match actual sources.
        
        Args:
            response: The model's response text
            minima_result: The result from Minima containing source information
            
        Returns:
            tuple: (verified_response, needs_retry)
        """
        if not minima_result or "source_paths" not in minima_result:
            return response, False
            
        source_paths = minima_result["source_paths"]
        if not source_paths:
            return response, False
            
        # Check for citations in the format [Source: path] or [Source: number]
        citation_pattern = r'\[Source:\s*([^\]]+)\]'
        citations = re.findall(citation_pattern, response)
        
        if not citations:
            # No citations found, add a warning
            warning = "\n\n⚠️ WARNING: No sources were cited. Please cite your sources using the format [Source: handbook.hypha.coop/path/to/document]"
            return response + warning, True
            
        # Verify each citation
        invalid_citations = []
        for citation in citations:
            # Check if it's a number citation
            if citation.strip().isdigit():
                num = int(citation.strip())
                if 1 <= num <= len(source_paths):
                    # Replace number with actual path
                    actual_path = source_paths[num-1]
                    response = response.replace(f"[Source: {citation}]", f"[Source: {actual_path}]")
                else:
                    invalid_citations.append(citation)
            # Check if it's a path citation
            elif not any(citation.strip() == path for path in source_paths):
                invalid_citations.append(citation)
                
        if invalid_citations:
            warning = f"\n\n⚠️ WARNING: The following citations are invalid: {', '.join(invalid_citations)}. Please use only the exact source paths provided."
            return response + warning, True
            
        return response, False
    
    def make_system(self):
        """
        Create an enhanced system prompt that mentions Minima document access.
        
        Returns:
            str: System prompt
        """
        base_prompt = super().make_system()
        system_messages = self._build_system_messages()
        
        if system_messages:
            return base_prompt + "\n\n" + "\n\n".join(system_messages)
        
        return base_prompt
    
    def is_minima_connected(self):
        """Check if Minima is connected."""
        return self.minima_adapter.using_minima and self.minima_adapter.is_connected()
    
    async def close(self):
        """Close connections and clean up resources."""
        if self.minima_adapter and self.minima_adapter.is_connected():
            await self.minima_adapter.close()


def make_roollm_with_minima(inference, tool_list=None, config=None):
    """
    Factory function to create a RooLLMWithMinima instance.
    
    This function creates a RooLLMWithMinima instance. The connection
    will be made when the chat method is first called.
    
    Args:
        inference: Inference function for the LLM
        tool_list: List of tools to load
        config: Configuration dictionary
        
    Returns:
        RooLLMWithMinima: The created instance
    """
    roollm = RooLLMWithMinima(inference, tool_list, config)
    return roollm 