"""Parser mínimo de S-expresiones para el protocolo de rcssserver."""


def parse(msg):
    """Convierte '(see 12 ((b) 3 4))' en ['see', '12', [['b'], '3', '4']]."""
    stack = [[]]
    token = ''
    in_str = False
    for ch in msg:
        if in_str:
            token += ch
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            token += ch
        elif ch == '(':
            if token:
                stack[-1].append(token)
                token = ''
            stack.append([])
        elif ch == ')':
            if token:
                stack[-1].append(token)
                token = ''
            if len(stack) > 1:
                done = stack.pop()
                stack[-1].append(done)
        elif ch in ' \t\n\x00':
            if token:
                stack[-1].append(token)
                token = ''
        else:
            token += ch
    if token:
        stack[-1].append(token)
    root = stack[0]
    return root[0] if len(root) == 1 else root
