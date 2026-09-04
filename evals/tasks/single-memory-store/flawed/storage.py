from typing import Protocol


class Store(Protocol):
    def put(self, key: str, payload: dict) -> None: ...


class MemoryStore:
    def __init__(self):
        self.items: dict[str, dict] = {}

    def put(self, key: str, payload: dict) -> None:
        self.items[key] = payload


class StoreFactory:
    @staticmethod
    def create() -> Store:
        return MemoryStore()
