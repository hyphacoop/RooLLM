import operator as op
import ast

name = 'calc'
description = 'Execute some simple math. E.g. 4 * (20 / 6^9)'
parameters = {
    'type': 'object',
    'properties': {
        'message': {
            'expression': 'string'
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
    match node:
        case ast.Constant(value) if isinstance(value, int):
            return value  # integer
        case ast.BinOp(left, op, right):
            return operators[type(op)](eval_(left), eval_(right))
        case ast.UnaryOp(op, operand):  # e.g., -1
            return operators[type(op)](eval_(operand))
        case _:
            raise TypeError(node)


async def tool(roo, arguments, user):
    expression = arguments["expression"]
    result = eval_expr(expression)
    return f"Tell {user}, {expression} = {result}"
