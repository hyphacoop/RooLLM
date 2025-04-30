try:
    from ..tool_registry import Tool, ToolRegistry
except ImportError:
    try:
        from tool_registry import Tool, ToolRegistry
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent))
        from tool_registry import Tool, ToolRegistry

Tools = ToolRegistry
__all__ = ['Tools', 'Tool']