from upload import Upload


def document_upload(name: str, content: bytes, content_type: str) -> Upload:
    return Upload(name, content, content_type, False)


def avatar_upload(name: str, content: bytes, content_type: str) -> Upload:
    return Upload(name, content, content_type, True)


def export_upload(name: str, content: bytes, content_type: str) -> Upload:
    return Upload(name, content, content_type, False)
