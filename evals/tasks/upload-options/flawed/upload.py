from dataclasses import dataclass


@dataclass(frozen=True)
class Upload:
    name: str
    content: bytes
    content_type: str
    private: bool


class UploadBuilder:
    def __init__(self, name: str, content: bytes):
        self._name = name
        self._content = content
        self._content_type = "application/octet-stream"
        self._private = False

    def content_type(self, value: str):
        self._content_type = value
        return self

    def private(self, value: bool):
        self._private = value
        return self

    def build(self) -> Upload:
        return Upload(
            self._name, self._content, self._content_type, self._private
        )
