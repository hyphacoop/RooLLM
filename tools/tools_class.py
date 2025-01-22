
import importlib


class Tools:
    def __init__(self, tools=None):
        self.tools = {}

    def load_tool(self, name):
        try:
            # Import the tool module using the package system
            module = importlib.import_module(f".{name}", package=__package__)
            self.tools[name] = module
        except ImportError as e:
            raise ImportError(f"Failed to import tool '{name}': {str(e)}")

    def descriptions(self):
        return [self.description_of(key) for key in self.tools.keys()]

    def description_of(self, name):
        module = self.tools[name]
        return {
            'type': 'function',
            'function': {
                'name': name,
                'description': module.description,
                'parameters': module.parameters,
                'emoji': module.emoji
            }
        }

    def call(self, roo, name, args, user):
        module = self.tools[name]
        func = module.tool
        return func(roo, args, user)

    def subset(self, list):
        tools = {}
        for name in list:
            tools[name] = self.tools[name]
        return Tools(tools)

    def get_tool_emoji(self, tool_name):
        """
        Fetches the emoji associated with a tool by looking up its metadata.
        :param tool_name: The name of the tool whose emoji is being retrieved.
        :param tools: The Tools instance to fetch metadata from.
        :return: The emoji associated with the tool (if any).
        """
        try:
            tool_description = self.description_of(tool_name)
            return tool_description.get("function", {}).get("emoji")
        except KeyError:
            return "❓"
