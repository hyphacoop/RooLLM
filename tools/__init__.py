try:
    from ..tool_registry import Tool, ToolRegistry
except ImportError:
    from tool_registry import Tool, ToolRegistry

Tools = ToolRegistry
__all__ = ['Tools', 'Tool']