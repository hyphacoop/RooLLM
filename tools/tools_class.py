
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