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


def tool(roo, arguments):
    print("ECHO TOOL: " + arguments["message"])
    return "Message sent successfully"
