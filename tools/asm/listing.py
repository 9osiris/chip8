"""Listing files: address, bytes, and source side by side."""


class Listing:
    def __init__(self):
        self.entries = []  # (addr, data: bytes, text)

    def add(self, addr, data, text):
        self.entries.append((addr, bytes(data), text.strip()))

    def render(self):
        lines = []
        for addr, data, text in self.entries:
            if data:
                hexs = " ".join(f"{b:02X}" for b in data)
                lines.append(f"{addr:04X}: {hexs:<14} {text}")
            else:
                lines.append(f"{addr:04X}: {'':<14} {text}")
        return "\n".join(lines) + "\n"

    def write(self, path):
        with open(path, "w") as f:
            f.write(self.render())
