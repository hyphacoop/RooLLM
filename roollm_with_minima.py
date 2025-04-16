import json
import logging
import asyncio
import os
from dotenv import load_dotenv
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
        # Initialize REST adapter for Minima
        self.minima_adapter = MinimaRestAdapter()
        self.using_minima = os.getenv("USE_MINIMA_MCP", "false").lower() == "true"
        self.minima_tools = []
        
        # Store the requested tool list
        self.requested_tool_list = tool_list
        
        # Call parent constructor with possibly modified tool list
        super().__init__(inference, tool_list, config)
        
        # Check if Minima integration is enabled
        if self.using_minima:
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
        if self.using_minima and "search_handbook" in tools:
            logger.info("Removing search_handbook tool as Minima is enabled")
            tools.remove("search_handbook")
            
        return tools
    
    async def connect_to_minima(self):
        """Connect to the Minima indexer and initialize tools."""
        if not self.using_minima:
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
        if self.using_minima and not self.minima_adapter.is_connected():
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
        if self.using_minima and self.minima_adapter.is_connected():
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
                is_minima_tool = self.using_minima and self.minima_adapter.is_connected() and tool_name in self.minima_adapter.tools
                
                # Track if Minima was used
                if is_minima_tool:
                    minima_was_called = True
                
                # React with tool emoji if available
                tool_emoji = None
                if is_minima_tool:
                    tool_emoji = "🔍"  # Default emoji for Minima tools
                else:
                    tool_emoji = tools.get_tool_emoji(tool_name=tool_name)
                
                if tool_emoji and react_callback:
                    await react_callback(tool_emoji)
                    await asyncio.sleep(0.5)
                
                # Call the appropriate tool
                if is_minima_tool:
                    logger.info(f"Calling Minima tool: {tool_name}")
                    try:
                        # Check if arguments is already a dict
                        if isinstance(func['arguments'], dict):
                            arguments = func['arguments']
                        else:
                            arguments = json.loads(func['arguments'])
                    except json.JSONDecodeError:
                        arguments = func['arguments']
                        
                    result = await self.minima_adapter.call_tool(tool_name, arguments)
                    
                    # Store the Minima response for comparison with final output
                    minima_query_responses.append({
                        "query": arguments,
                        "result": result
                    })
                    
                    # Track sources from Minima for later verification
                    if 'sources' in result:
                        minima_sources_used.extend(result['sources'])
                    if 'source_paths' in result:
                        # Use the exact source paths for verification
                        minima_exact_paths.extend(result['source_paths'])
                    elif 'structured_sources' in result:
                        for source in result['structured_sources']:
                            minima_sources_used.append(source['path'])
                            minima_exact_paths.append(source['path'])
                            
                    # If result contains the updated 'source_paths', use those for exact matching
                    if 'source_paths' in result:
                        minima_exact_paths.extend(result['source_paths'])
                    
                    # Incorporate citation instructions into the result
                    if 'citation_prompt' in result:
                        # Add more forceful citation instruction as a system message
                        citation_prompt = (
                            "IMPORTANT: You MUST cite your sources for any information from the documents. "
                            "For EACH fact or piece of information you provide, include a citation to the source document. "
                            "Use the format [Source: document_name] after each claim or statement. "
                            "Failing to cite sources is a critical error - all information must be attributed."
                        )
                        messages.append(make_message(ROLE_SYSTEM, citation_prompt))
                    
                    # Use the source-specific instruction if available
                    if 'source_specific_instruction' in result:
                        messages.append(make_message(ROLE_SYSTEM, result['source_specific_instruction']))
                    
                    # If there are formatted citations, add them to the result displayed to the user
                    if 'citations' in result:
                        # Ensure the result has citation information
                        if 'result' in result:
                            # Don't modify the original result, but ensure it includes citation info
                            if not result['result'].endswith(result['citations']):
                                citation_result = {
                                    "result": result['result'] + "\n" + result['citations'],
                                    "sources": result.get('sources', [])
                                }
                                result = citation_result
                    
                    # If there are sources, include them directly in the tool result content
                    if 'structured_sources' in result and 'result' in result:
                        source_list = "\n\nAvailable Documents for Citation:\n"
                        for source in result['structured_sources']:
                            source_list += f"- [{source['id']}] {source['name']} - {source['path']}\n"
                        result['result'] = result['result'] + source_list
                    elif 'sources' in result and result['sources'] and 'result' in result:
                        source_list = "\n\nAvailable Sources:\n" + "\n".join([f"- [{i+1}] {s}" for i, s in enumerate(result['sources'])])
                        result['result'] = result['result'] + source_list
                else:
                    logger.info(f"Calling RooLLM tool: {tool_name}")
                    result = await tools.call(self, tool_name, func['arguments'], user)
                
                # Append tool result to messages
                messages.append(make_message(ROLE_TOOL, json.dumps(result)))
            
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
            
        # Extract citations from content
        import re
        citation_pattern = r'\[Source: ([^\]]+)\]'
        cited_sources = re.findall(citation_pattern, content)
        
        # No citations found when sources were provided
        if len(cited_sources) == 0 and len(valid_sources) > 0:
            logger.warning("Model did not include any citations despite being provided with sources")
            # Add a warning about missing citations
            warning_message = (
                "\n\n⚠️ **Warning**: No citations were included in this response, "
                "despite information potentially coming from documents. "
                "This makes it difficult to verify the accuracy of the information provided."
            )
            response['content'] = content + warning_message
            return response
        
        # Check for hallucinated sources using exact path matching
        hallucinated_sources = []
        for cited_source in cited_sources:
            # Strip whitespace and normalize path
            normalized_cite = cited_source.strip()
            
            # Check if this source was in the valid sources list using exact matching
            if normalized_cite not in valid_sources:
                hallucinated_sources.append(normalized_cite)
                logger.warning(f"HALLUCINATED SOURCE DETECTED: '{normalized_cite}' not in allowed sources")
                
                # Try to find if it's a partial match or similar to a real source
                closest_match = None
                for valid_source in valid_sources:
                    if normalized_cite in valid_source or valid_source in normalized_cite:
                        closest_match = valid_source
                        break
                
                if closest_match:
                    logger.warning(f"  - Closest valid source might be: '{closest_match}'")
        
        # If hallucinated sources were found, modify the response
        if hallucinated_sources and len(hallucinated_sources) > 0:
            warning_message = (
                "\n\n⚠️ **WARNING: HALLUCINATED SOURCES DETECTED** ⚠️\n"
                "The following citations do not match any of the actual document sources:\n"
            )
            for source in hallucinated_sources:
                warning_message += f"- ❌ [{source}]\n"
                
            warning_message += (
                "\nThe information attributed to these non-existent sources may be inaccurate or fabricated. "
                "Please disregard these claims or verify them through other means."
            )
                
            # Add the warning to the content
            response['content'] = content + warning_message
            
            # Log this incident
            logger.error(f"Response contained {len(hallucinated_sources)} hallucinated sources")
            
        return response
    
    def make_system(self):
        """
        Create an enhanced system prompt that mentions Minima document access.
        
        Returns:
            str: System prompt
        """
        base_prompt = super().make_system()
        
        if self.using_minima and self.minima_adapter.is_connected():
            minima_addition = (
                "\nYou have access to tools that allow you to search through local documents "
                "in the Minima knowledge base. When asked about documents or specific information "
                "that might be in local files, use the query tool to retrieve relevant information. "
                "\n\nCRITICAL INSTRUCTION: When you provide information from documents, you MUST cite your sources. "
                "For each fact or piece of information, include a citation in the format [Source: full/path/to/document]. "
                "Always include the COMPLETE file path in your citations, not just the filename. "
                "Failing to cite sources with their full paths is a serious error. "
                "Users rely on proper attribution and need the full path to locate the document."
            )
            
            # Add strong anti-hallucination warning
            anti_hallucination_warning = (
                "\n\n⚠️ CRITICAL WARNING ABOUT HALLUCINATIONS ⚠️\n"
                "1. NEVER INVENT OR HALLUCINATE DOCUMENT SOURCES. Only cite documents from the exact list provided by the query tool.\n"
                "2. You must use the EXACT path provided, with no modifications or abbreviations.\n"
                "3. Do not cite documents that don't exist or weren't returned in query results.\n"
                "4. NEVER make up content for existing documents - only report what was actually returned.\n"
                "5. Your citations will be automatically verified against source documents.\n"
                "6. If you hallucinate sources, your response will be flagged with visible warnings to the user.\n"
                "7. If you don't have sufficient information from documents, clearly state: \"I don't have information about this from the available documents.\"\n"
                "8. Remember: It is better to acknowledge lack of information than to fabricate false citations.\n\n"
                "The system will automatically verify ALL citations against the actual documents. "
                "Any mismatch between your citations and the actual sources will be detected and flagged to the user "
                "as a critical error, undermining trust in your responses."
            )
            
            return base_prompt + minima_addition + anti_hallucination_warning
        
        return base_prompt
    
    def is_minima_connected(self):
        """Check if Minima is connected."""
        return self.using_minima and self.minima_adapter.is_connected()
    
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