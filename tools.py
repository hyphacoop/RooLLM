import importlib
import importlib.util
import os


class Tools:
    def __init__(self, tools={}):
        self.tools = {}

    def load_tool(self, name):
        tool_path = f"tools/{name}.py"
        module = load_module_from_file(tool_path)
        self.tools[name] = module

    def descriptions(self):
        return [self.description_of(key) for key in self.tools.keys()]

    def description_of(self, name):
        module = self.tools[name]
        return {
            'type': 'function',
            'function': {
                'name': name,
                'description': module.description,
                'parameters': module.parameters
            }
        }

    def call(self, roo, name, args):
        module = self.tools[name]
        func = module.tool
        return func(roo, args)

    def subset(self, list):
        tools = {}
        for name in list:
            tools[name] = self.tools[name]
        return Tools(tools)


def load_module_from_file(file_path):
    root = os.path.dirname(__file__)
    # Construct the module name based on the file path
    module_name = os.path.basename(file_path).replace('.py', '')

    full_path = os.path.join(root, file_path)

    # Create a spec for the module
    spec = importlib.util.spec_from_file_location(module_name, full_path)

    # Load the module
    module = importlib.util.module_from_spec(spec)

    # Execute the module's code in its own namespace
    spec.loader.exec_module(module)

    return module
