"""Transport-only SSE comment filtering for the Gemini SDK's data-only parser."""

class CommentFilter:
    def __init__(self):
        self.pending = b''
        self.removed = 0

    def feed(self, chunk):
        self.pending += chunk
        output = []
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            if line.startswith(b':'):
                self.removed += 1
            else:
                output.append(line + b'\n')
        return b''.join(output)

    def finish(self):
        tail, self.pending = self.pending, b''
        if tail.startswith(b':'):
            self.removed += 1
            return b''
        return tail
