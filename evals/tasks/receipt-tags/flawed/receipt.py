from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    identifier: str
    channel: str
    status: str
    tags: tuple[str, ...]


class ReceiptBuilder:
    def __init__(self, identifier: str, channel: str):
        self._identifier = identifier
        self._channel = channel
        self._status = "queued"
        self._tags: tuple[str, ...] = ()

    def with_status(self, status: str):
        self._status = status
        return self

    def with_tags(self, tags: tuple[str, ...]):
        self._tags = tags
        return self

    def build(self) -> Receipt:
        return Receipt(
            self._identifier, self._channel, self._status, self._tags
        )
