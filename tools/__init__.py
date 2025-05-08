try:
    from .tool_registry import Tool, ToolRegistry
except ImportError:
    from tools.tool_registry import Tool, ToolRegistry
    
__all__ = ['Tool', 'ToolRegistry']