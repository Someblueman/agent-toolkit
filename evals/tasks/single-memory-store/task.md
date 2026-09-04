`MemoryStore` is now the only event-store implementation. `save_event` writes
every payload under the literal key `event` instead of the caller's key. Fix
that behavior. Storage APIs are internal to this repository, and callers must
still receive the populated store from `save_event`.
