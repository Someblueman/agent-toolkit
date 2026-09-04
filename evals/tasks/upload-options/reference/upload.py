from dataclasses import dataclass


@dataclass(frozen=True)
class Upload:
    name: str
    content: bytes
    content_type: str
    private: bool
