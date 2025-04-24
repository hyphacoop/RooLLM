from typing import Dict, Any, List, Optional

class Tool:
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any], adapter_name: str = None, run_fn=None, emoji: Optional[str] = None):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.adapter_name = adapter_name
        self.run_fn = run_fn 
        self.emoji = emoji

    def to_openai_format(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }
    
    @classmethod
    def from_dict(cls, d: dict, adapter_name: str = None):
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            input_schema=d.get("parameters", {}), 
            adapter_name=adapter_name
        )

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def openai_descriptions(self) -> List[Dict]:
        return [tool.to_openai_format() for tool in self.all_tools()] 