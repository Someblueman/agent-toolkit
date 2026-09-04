class MemoryStore:
    def __init__(self):
        self.items: dict[str, dict] = {}

    def put(self, key: str, payload: dict) -> None:
        self.items[key] = payload
