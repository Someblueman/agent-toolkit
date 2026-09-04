from storage import Store, StoreFactory


def save_event(key: str, payload: dict) -> Store:
    store = StoreFactory.create()
    store.put("event", payload)
    return store
