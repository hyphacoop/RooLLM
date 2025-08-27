import anthropic
import logging
import re
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
            return "Please provide a search query to search the internet."
        
        # Get max_tokens with default and bounds
        max_tokens = arguments.get("max_tokens", 1024)
        max_tokens = max(100, min(4000, int(max_tokens)))
        
        # Get Claude API key from config
        api_key = roo.config.get("CLAUDE_API_KEY")
        if not api_key:
            logger.error("CLAUDE_API_KEY not found in configuration")
            return "Web search is not available - Claude API key is not configured."
        
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
            
            # Clean citation markers from the response
            cleaned_response = full_response
            # Remove citation markers but be more specific
            cleaned_response = re.sub(r'【[^】]*citations[^】]*】', '', cleaned_response)
            cleaned_response = re.sub(r'【[^】]*web_search[^】]*】', '', cleaned_response)
            # Clean up any extra whitespace and normalize
            cleaned_response = re.sub(r'\s+', ' ', cleaned_response).strip()
            
            # Format the response with search results and citations
            formatted_response = cleaned_response
            
            # Add sources section with clickable links
            logger.debug(f"Citations found: {len(citations)}, Search results found: {len(search_results)}")
            
            if search_results or citations:
                formatted_response += "\n\n**Sources:**\n"
                
                # Collect unique sources, prioritizing citations
                sources = []
                seen_urls = set()
                
                # Add citations first (they're more specific)
                for citation in citations[:3]:
                    url = citation.get('url', '').strip()
                    title = citation.get('title', 'Source').strip()
                    if url and url.startswith('http') and url not in seen_urls:
                        sources.append({
                            'title': title or 'Source',
                            'url': url
                        })
                        seen_urls.add(url)
                        logger.debug(f"Added citation: {title} - {url}")
                
                # Add search results (avoiding duplicates)
                for result in search_results[:3]:
                    url = result.get('url', '').strip()
                    title = result.get('title', 'Source').strip()
                    if url and url.startswith('http') and url not in seen_urls:
                        sources.append({
                            'title': title or 'Source',
                            'url': url
                        })
                        seen_urls.add(url)
                        logger.debug(f"Added search result: {title} - {url}")
                
                # Format the sources with simple numbering
                for i, source in enumerate(sources[:5], 1):
                    formatted_response += f"[{i}] [{source['title']}]({source['url']})\n"
                
                logger.debug(f"Final sources count: {len(sources)}")
            else:
                logger.debug("No sources found to add")
            
            logger.info(f"Web search completed successfully for query: {query}")
            logger.info(f"Found {len(search_results)} search results and {len(citations)} citations")
            logger.debug(f"Final formatted response: {formatted_response}")
            
            return formatted_response
        else:
            logger.warning(f"No content returned from Claude for query: {query}")
            return "I was unable to get a response from the web search. Please try again with a different query."
            
    except anthropic.APIError as e:
        logger.error(f"Claude API error during web search: {e}")
        return "I encountered an API error while searching. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error during web search: {str(e)}", exc_info=True)
        return "I encountered an unexpected error while searching. Please try again or rephrase your query."
