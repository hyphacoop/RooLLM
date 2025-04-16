import json
import logging
import asyncio
import os
from dotenv import load_dotenv

# Use try-except pattern for imports that can work both in package mode and standalone mode
try:
    from .roollm import RooLLM, make_message, ROLE_TOOL, ROLE_SYSTEM, BASE_TOOL_LIST
    from .minima_adapter import MinimaRestAdapter
except ImportError:
    from roollm import RooLLM, make_message, ROLE_TOOL, ROLE_SYSTEM, BASE_TOOL_LIST
    from minima_adapter import MinimaRestAdapter

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
    
    def _handle_minima_result(self, result, messages):
        """
        Handle the result from a Minima tool call and update messages accordingly.
        
        Args:
            result: The result from Minima
            messages: List of messages to update
            
        Returns:
            dict: Processed result
        """
        processed_result = result.copy()
        
        # Add citation instructions if needed
        if 'citation_prompt' in result:
            citation_prompt = (
                "IMPORTANT: You MUST cite your sources for any information from the documents. "
                "For EACH fact or piece of information you provide, include a citation to the source document. "
                "Use the format [Source: handbook.hypha.coop/path/to/document] after each claim or statement. "
                "Failing to cite sources is a critical error - all information must be attributed."
            )
            messages.append(make_message(ROLE_SYSTEM, citation_prompt))
        
        # Add source-specific instruction if available
        if 'source_specific_instruction' in result:
            messages.append(make_message(ROLE_SYSTEM, result['source_specific_instruction']))
        
        # Handle citations in result
        if 'citations' in result and 'result' in result:
            if not result['result'].endswith(result['citations']):
                processed_result = {
                    "result": result['result'] + "\n" + result['citations'],
                    "sources": result.get('sources', [])
                }
        
        # Add source list to result
        if 'structured_sources' in result and 'result' in result:
            source_list = "\n\nAvailable Documents for Citation:\n"
            source_list += "\n".join(f"- [{source['id']}] {source['name']} - {source['path']}" 
                                   for source in result['structured_sources'])
            processed_result['result'] = result['result'] + source_list
        elif 'sources' in result and result['sources'] and 'result' in result:
            source_list = "\n\nAvailable Sources:\n" + "\n".join(
                f"- [{i+1}] {s}" for i, s in enumerate(result['sources']))
            processed_result['result'] = result['result'] + source_list
            
        return processed_result

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
            sources.extend(result['sources'])
        if 'source_paths' in result:
            exact_paths.extend(result['source_paths'])
        elif 'structured_sources' in result:
            for source in result['structured_sources']:
                sources.append(source['path'])
                exact_paths.append(source['path'])
                
        return sources, exact_paths

    def _build_system_messages(self):
        """
        Build system messages for Minima integration.
        
        Returns:
            list: List of system messages
        """
        messages = []
        
        if self.minima_adapter.using_minima and self.minima_adapter.is_connected():
            # Base Minima message
            messages.append(
                "You can search documents using the query tool. "
                "When using document information, cite sources with [Source: handbook.hypha.coop/path/to/document]."
            )
            
            # Anti-hallucination warning
            messages.append(
                "Only cite documents that were returned by the query tool. "
                "If you don't have information from the documents, say so."
            )
            
            # Usage instructions
            messages.append(
                "Use the document content to answer questions. "
                "Cite sources properly."
            )
            
        return messages

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
        
        # Try to connect to Minima automatically if it's enabled and not connected
        if self.minima_adapter.using_minima and not self.minima_adapter.is_connected():
            await self.connect_to_minima()
        
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
        if self.minima_adapter.using_minima and self.minima_adapter.is_connected():
            # If the query seems to be asking about documents or knowledge, automatically use Minima
            if any(keyword in content.lower() for keyword in ['what is', 'how to', 'where is', 'when is', 'who is', 'check', 'look', 'find', 'search', 'policy', 'procedure', 'guide', 'handbook']):
                # For document queries, only use Minima tools
                combined_tools = self.minima_tools
                logger.info(f"Using only Minima tools for document query")
                
                # Add a system message to encourage using Minima
                minima_reminder = make_message(ROLE_SYSTEM, 
                    "Answer the question using only the document content provided. "
                    "Cite sources using [Source: handbook.hypha.coop/path/to/document]."
                )
                messages.append(minima_reminder)
                
                # Execute the Minima query directly
                logger.info(f"Executing automatic Minima query for: {content}")
                try:
                    result = await self.minima_adapter.call_tool("query", {"text": content})
                    
                    # Add the query result to messages
                    if "error" in result:
                        messages.append(make_message(ROLE_TOOL, json.dumps({
                            "error": result["error"]
                        })))
                    else:
                        messages.append(make_message(ROLE_TOOL, json.dumps(result)))
                        
                        # Add citation instructions if we got results
                        if "sources" in result and result["sources"]:
                            pass

                except Exception as e:
                    logger.error(f"Error executing automatic Minima query: {e}")
                    messages.append(make_message(ROLE_TOOL, json.dumps({
                        "error": f"Failed to execute Minima query: {str(e)}"
                    })))
            else:
                combined_tools = tool_descriptions + self.minima_tools
                logger.info(f"Using {len(tool_descriptions)} RooLLM tools and {len(self.minima_tools)} Minima tools")
        else:
            combined_tools = tool_descriptions
            logger.info(f"Using {len(tool_descriptions)} RooLLM tools (Minima not connected)")
        
        # For tracking Minima usage and sources
        minima_sources_used = []
        minima_exact_paths = []
        minima_was_called = False
        minima_query_responses = []  # Track the responses from Minima
        
        # Send first request to the LLM
        response = await self.inference(messages, combined_tools)
        
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
                        processed_result = self._handle_minima_result(result, messages)
                        
                    except Exception as e:
                        logger.error(f"Error executing Minima tool: {e}")
                        processed_result = {
                            "error": f"Failed to execute Minima query: {str(e)}"
                        }
                else:
                    logger.info(f"Calling RooLLM tool: {tool_name}")
                    processed_result = await tools.call(self, tool_name, func['arguments'], user)
                
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
            response = self._verify_citations_in_response(response, verify_against)
            
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
            
        # Remove .md extension if present
        if clean_path.endswith('.md'):
            clean_path = clean_path[:-3]
            
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

    def _verify_citations_in_response(self, response, valid_sources):
        """
        Verify that citations in the response match actual sources.
        Detect potential hallucinated sources and add warnings if needed.
        
        Args:
            response: The model's response
            valid_sources: List of valid source paths that were provided to the model
            
        Returns:
            dict: Modified response with warnings if needed
        """
        content = response.get('content', '')
        if not content:
            return response
            
        # Transform all valid sources to handbook.hypha.coop format
        transformed_sources = [self._transform_source_path(source) for source in valid_sources]
        
        # Extract citations from content
        cited_sources = self._extract_citations(content)
        
        # No citations found when sources were provided
        if not cited_sources and transformed_sources:
            logger.warning("No citations found in response despite available sources")
            response['content'] = content + self._create_warning_message('no_citations')
            return response
        
        # Check for hallucinated sources
        hallucinated_sources = []
        for citation in cited_sources:
            if not self._find_closest_match(citation, transformed_sources):
                hallucinated_sources.append(citation)
                logger.warning(f"HALLUCINATED SOURCE DETECTED: '{citation}' not in allowed sources")
        
        # Add warning if hallucinated sources found
        if hallucinated_sources:
            response['content'] = content + self._create_warning_message('hallucinated_sources', hallucinated_sources)
            logger.error(f"Response contained {len(hallucinated_sources)} hallucinated sources")
            
        return response
    
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