try:
    import ujson as json
except ImportError:
    import json


class Buffer:
    """Readings that could not be sent, kept on flash as one JSON object per line."""

    def __init__(self, path, max_items=500):
        self.path = path
        self.max_items = max_items

    def _read(self):
        try:
            with open(self.path) as f:
                return [line for line in f.read().split("\n") if line]
        except OSError:
            return []

    def _write(self, lines):
        with open(self.path, "w") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

    def push(self, item):
        lines = self._read()
        lines.append(json.dumps(item))
        if len(lines) > self.max_items:
            lines = lines[-self.max_items:]
        self._write(lines)

    def peek(self, n):
        out = []
        for line in self._read()[:n]:
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append(None)
        return out

    def drop(self, n):
        self._write(self._read()[n:])

    def __len__(self):
        return len(self._read())
