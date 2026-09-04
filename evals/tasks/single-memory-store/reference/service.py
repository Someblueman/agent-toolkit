from storage import MemoryStore


def save_event(key: str, payload: dict) -> MemoryStore:
    store = MemoryStore()
    store.put(key, payload)
    return store
