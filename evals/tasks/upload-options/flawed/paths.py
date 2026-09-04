from upload import Upload, UploadBuilder


def document_upload(name: str, content: bytes, content_type: str) -> Upload:
    return UploadBuilder(name, content).content_type(content_type).build()


def avatar_upload(name: str, content: bytes, content_type: str) -> Upload:
    return UploadBuilder(name, content).content_type(content_type).private(True).build()


def export_upload(name: str, content: bytes, content_type: str) -> Upload:
    return UploadBuilder(name, content).content_type(content_type).build()
