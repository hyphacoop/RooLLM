import anthropic
import logging
import os
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Tool configuration
name = "web_search"
emoji = "🌐"
description = (
    "Search the internet for current information using Claude with web search capabilities. "
    "Use this tool when you need to find up-to-date information, current events, recent news, "
    "or any information that may not be in your training data. The tool will search the web "
    "and provide a comprehensive answer based on the latest available information."
)
parameters = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query or question to search for on the internet. Be specific and clear about what information you're looking for."
        },
        "max_tokens": {
            "type": "integer",
            "description": "Maximum number of tokens for the response. Defaults to 1024.",
            "default": 1024,
            "minimum": 100,
            "maximum": 4000
        }
    },
    "required": ["query"]
}


async def tool(roo, arguments: Dict[str, Any], user: str) -> Dict[str, Any]:
    """
    Tool function to perform web search using Claude with web search capabilities.
    
    Args:
        roo: RooLLM instance
        arguments: Dictionary of arguments from the LLM
        user: User identifier
        
    Returns:
        Dictionary with search results and response
    """
    
    try:
        # Extract query from arguments
        query = arguments.get("query")
        if not query:
            return {
                "error": "No search query provided",
                "message": "Please provide a search query to search the internet."
            }
        
        # Get max_tokens with default and bounds
        max_tokens = arguments.get("max_tokens", 1024)
        max_tokens = max(100, min(4000, int(max_tokens)))
        
        # Get Claude API key from config
        api_key = roo.config.get("CLAUDE_API_KEY")
        if not api_key:
            logger.error("CLAUDE_API_KEY not found in configuration")
            return {
                "error": "Claude API key not configured",
                "message": "Web search is not available - Claude API key is not configured."
            }
        
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=api_key)
        
        # Create the search prompt
        search_prompt = f"""Search the internet for current information about: {query}

Provide a concise, accurate answer based on the most recent information available. 
Include key facts, numbers, and context. Be direct and to the point while maintaining accuracy.

For queries about:
- Prices/financial data: Include current values, recent changes, and key metrics
- Current events: Include latest developments and dates
- Technical info: Include essential details and documentation
- General knowledge: Include key facts and context

Keep responses focused, concise, and avoid unnecessary elaboration. If no relevant results, suggest alternative search terms."""

        logger.info(f"Performing web search for query: {query}")
        
        # Call Claude API with web search tool
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": search_prompt
            }],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            }]
        )
        
        # Extract the response content and search results
        if response.content and len(response.content) > 0:
            # Process the response content to extract text and search results
            text_parts = []
            search_results = []
            citations = []
            
            for content_item in response.content:
                if hasattr(content_item, 'type'):
                    if content_item.type == 'text':
                        text_parts.append(content_item.text)
                        # Also check for citations in text content
                        if hasattr(content_item, 'citations') and content_item.citations:
                            for citation in content_item.citations:
                                if hasattr(citation, 'type') and citation.type == 'web_search_result_location':
                                    citations.append({
                                        'url': getattr(citation, 'url', ''),
                                        'title': getattr(citation, 'title', ''),
                                        'cited_text': getattr(citation, 'cited_text', '')
                                    })
                    elif content_item.type == 'web_search_tool_result':
                        # Extract search results
                        if hasattr(content_item, 'content'):
                            for result in content_item.content:
                                if hasattr(result, 'type') and result.type == 'web_search_result':
                                    search_results.append({
                                        'url': getattr(result, 'url', ''),
                                        'title': getattr(result, 'title', ''),
                                        'page_age': getattr(result, 'page_age', ''),
                                        'content_preview': getattr(result, 'encrypted_content', '')[:200] + '...' if hasattr(result, 'encrypted_content') else ''
                                    })
            
            # Combine all text parts
            full_response = ' '.join(text_parts)
            
            # Format the response with search results and citations
            formatted_response = full_response
            
            # Add sources section with clickable links
            if search_results or citations:
                formatted_response += "\n\n**Sources:**\n"
                
                # Combine search results and citations, prioritizing citations
                all_sources = []
                
                # Add citations first (they're more specific)
                for i, citation in enumerate(citations[:3], 1):
                    all_sources.append({
                        'index': i,
                        'title': citation['title'],
                        'url': citation['url'],
                        'type': 'citation'
                    })
                
                # Add search results (avoiding duplicates)
                existing_urls = {citation['url'] for citation in citations}
                for i, result in enumerate(search_results[:3], len(citations) + 1):
                    if result['url'] not in existing_urls:
                        all_sources.append({
                            'index': i,
                            'title': result['title'],
                            'url': result['url'],
                            'type': 'search_result'
                        })
                
                # Format the sources
                for source in all_sources[:5]:  # Limit to 5 sources max
                    formatted_response += f"[{source['index']}] [{source['title']}]({source['url']})\n"
                
                if len(search_results) + len(citations) > 5:
                    formatted_response += f"... and {len(search_results) + len(citations) - 5} more sources\n"
            
            logger.info(f"Web search completed successfully for query: {query}")
            logger.info(f"Found {len(search_results)} search results and {len(citations)} citations")
            
            return {
                "query": query,
                "response": full_response,
                "formatted_response": formatted_response,
                "search_results": search_results,
                "citations": citations,
                "message": formatted_response,
                "tool_used": "claude_web_search",
                "max_tokens_used": max_tokens,
                "sources_count": len(search_results),
                "citations_count": len(citations)
            }
        else:
            logger.warning(f"No content returned from Claude for query: {query}")
            return {
                "error": "No response from Claude",
                "message": "I was unable to get a response from the web search. Please try again with a different query."
            }
            
    except anthropic.APIError as e:
        logger.error(f"Claude API error during web search: {e}")
        return {
            "error": f"Claude API error: {str(e)}",
            "message": "I encountered an API error while searching. Please try again later."
        }
    except Exception as e:
        logger.error(f"Unexpected error during web search: {str(e)}", exc_info=True)
        return {
            "error": f"Search failed: {str(e)}",
            "message": "I encountered an unexpected error while searching. Please try again or rephrase your query."
        }
