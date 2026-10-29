def unquote(s):
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    raw = s.encode()
    while i < len(raw):
        if raw[i] == 0x25 and i + 2 < len(raw):
            try:
                out.append(int(raw[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(raw[i])
        i += 1
    return out.decode()


def parse(body):
    fields = {}
    for pair in body.split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        fields[unquote(k)] = unquote(v)
    return fields


def escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
