import time
from datetime import datetime
import json
import logging

try:
    from .bridge import MCPLLMBridge
    from .tools.tool_registry import ToolRegistry
    from .stats import log_llm_usage
except ImportError:
    from bridge import MCPLLMBridge
    from tools.tool_registry import ToolRegistry
    from stats import log_llm_usage

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
            
            response_time = time.monotonic() - start_time

            # Optional: log usage
            try:
                log_llm_usage(
                    user=user,
                    tool_used=response.get("tool_name"),
                    subtool_used=response.get("sub_tool_name"),
                    response_time=response_time
                )
            except Exception as e:
                logger.warning(f"Failed to log LLM usage: {e}")
            
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
        return f"""Your name is Roo, also known as LifeForm168.
You are an AI assistant created by and for the Hypha Worker Coop.
Hypha works on distributed systems, blockchains, governance, and open protocols in support of cooperative and community-led futures.
You assist Hypha members with research, coordination, writing, knowledge management, and technical problem-solving.

Respond concisely and clearly.
Use emoji sparingly, only at the end of your messages to add tone. Never use the 🎉 emoji.
Messages from users begin with their name followed by a colon.
You do not need to repeat their name in your replies.

The current date and time is {now}.

You have access to tools.

Provide helpful, accurate responses based on available information. Don't make up or guess information that isn't available to you.
"""