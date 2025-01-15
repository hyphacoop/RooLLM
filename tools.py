import importlib
import importlib.util
import os


class Tools:
    def __init__(self, tools={}):
        self.tools = {}

    def load_tool(self, name):
        root = os.path.dirname(os.path.abspath(__file__))  # Absolute path to the directory of tools.py
        tool_path = os.path.join(root, "tools", f"{name}.py")  # Append the tool file

        # Check if the tool file exists
        if not os.path.isfile(tool_path):
            raise FileNotFoundError(f"Tool file not found at: {tool_path}")

        # Load the module
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

    def call(self, roo, name, args, user):
        module = self.tools[name]
        func = module.tool
        return func(roo, args, user)

    def subset(self, list):
        tools = {}
        for name in list:
            tools[name] = self.tools[name]
        return Tools(tools)


def load_module_from_file(file_path):
    full_path = os.path.abspath(file_path) 

    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"Cannot load module, file does not exist: {full_path}")

    module_name = os.path.basename(file_path).replace('.py', '')

    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)
    return module
