Uploads created by the document, avatar, and export paths are losing their
content type and falling back to `application/octet-stream`. Preserve the
supplied content type in all three paths. Upload construction is internal to
this repository; keep the change focused and update affected call sites.
