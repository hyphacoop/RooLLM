import operator as op
import ast

name = 'calc'
emoji = '🔢'
description = 'Execute some simple math. E.g. 4 * (20 / 6^9) ** 0.5'
parameters = {
    'type': 'object',
    'properties': {
        'message': {
            'expression': {
                'type': 'string'
            }
        }
    },
    'required': ['expression']
}

# Based on https://stackoverflow.com/a/9558001

# supported operators
operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg}


def eval_expr(expr):
    return eval_(ast.parse(expr, mode='eval').body)


def eval_(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value  # integer or float
    elif isinstance(node, ast.BinOp):
        return operators[type(node.op)](eval_(node.left), eval_(node.right))
    elif isinstance(node, ast.UnaryOp):  # e.g., -1
        return operators[type(node.op)](eval_(node.operand))
    else:
        raise TypeError(node)


async def tool(roo, arguments, user, extra_context=None):
    expression = arguments["expression"]
    result = eval_expr(expression)
    return f"Tell {user}, {expression} = {result}"
