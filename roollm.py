import time
from datetime import datetime
import json
import logging

try:
    from .bridge import MCPLLMBridge
    from .tools.tool_registry import ToolRegistry
except ImportError:
    from bridge import MCPLLMBridge
    from tools.tool_registry import ToolRegistry

# Configure logging
logger = logging.getLogger(__name__)

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"


def make_message(role, content):
    return {
        "role": role,
        "content": content
    }

class RooLLM:
    def __init__(self, inference, config=None):
        """
        Initialize the RooLLM instance.
        
        Args:
            inference: LLMClient instance for model inference
            config: Configuration dictionary
        """
        self.inference = inference
        self.config = config or {}
        self.tool_registry = ToolRegistry()
        
        # Create and initialize the bridge
        self.bridge = MCPLLMBridge(
            llm_client=inference,
            config=config,
            tool_registry=self.tool_registry,
            roollm=self
        )
        logger.debug("RooLLM instance created")

    async def initialize(self):
        """Initialize the RooLLM instance and load all tools."""
        logger.debug("Initializing RooLLM...")
        await self.bridge.initialize()
        logger.debug("RooLLM initialization complete")

    async def chat(self, user, content, history=[], react_callback=None):
        """
        Process a chat message and return a response.
        
        Args:
            user: User identifier
            content: Message content
            history: Conversation history
            react_callback: Callback for tool reactions
            
        Returns:
            Response message
        """
        system_message = make_message(ROLE_SYSTEM, self.make_system())
        
        # Format history with proper system message if not already present
        formatted_history = []
        if history and len(history) > 0:
            # Check if first message is a system message
            if history[0].get("role") == ROLE_SYSTEM:
                formatted_history = history
            else:
                # Add system message
                formatted_history = [system_message] + history
        else:
            formatted_history = [system_message]
            
        # Start timing
        start_time = time.monotonic()

        # Process the message
        try:
            response = await self.bridge.process_message(
                user=user,
                content=content,
                history=formatted_history,
                react_callback=react_callback
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Return a graceful error message
            return {
                "role": ROLE_ASSISTANT,
                "content": "I'm sorry, I encountered an error while processing your request. Please try again."
            }

    def update_config(self, new_config):
        """Update the configuration dictionary."""
        self.config.update(new_config)

    def make_system(self):
        """Create the system prompt for the LLM."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""
IMPORTANT: You operate in a ReAct (Reasoning and Acting) loop. When faced with complex tasks:
1. Think step by step about what you need to accomplish
2. Plan your approach by breaking down complex requests into smaller steps
3. Use tools to gather information and execute actions
4. Reason about the results of each tool call
5. Continue iterating until you have fully satisfied the user's intention
6. Provide a comprehensive final response

You can call multiple tools in sequence. After each tool call, analyze the results and determine:
- Did the tool provide the information or complete the action I needed?
- Do I need to call additional tools to fully address the user's request?
- What's my next step to move toward completing the user's goal?

CRITICAL: If the query tool returns insufficient information or says "no relevant documents found" or "does not explicitly mention":
- You MUST try alternative search queries with different keywords or phrasings
- Decompose the question into sub-topics and search for each separately
- Try broader or more specific search terms
- Continue searching until you find relevant information OR have exhausted reasonable search variations
- Only provide a final answer when you have found adequate information or tried multiple search approaches

Think out loud about your reasoning process. Explain what you're doing and why.

Respond concisely and clearly.
Use emoji sparingly, only at the end of your messages to add tone. Never use the 🎉 emoji.
Messages from users begin with their name followed by a colon.
You do not need to repeat their name in your replies.

The current date and time is {now}.

IMPORTANT: The knowledge base is automatically searched for every query to provide relevant context. You have access to the search results and should use them to provide accurate, well-informed responses.

Provide helpful, accurate responses based on the available information from the knowledge base. Always cite sources when using information from the knowledge base. Don't make up or guess information that isn't available to you.
"""