from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    identifier: str
    channel: str
    status: str
    tags: tuple[str, ...]
