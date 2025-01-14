name = 'echo'
description = 'Output a message to the user.'
parameters = {
    'type': 'object',
    'properties': {
        'message': {
            'type': 'string'
        }
    },
    'required': ['message']
}


def tool(roo, arguments, user):
    return f"ECHO TOOL: " + arguments["message"]
