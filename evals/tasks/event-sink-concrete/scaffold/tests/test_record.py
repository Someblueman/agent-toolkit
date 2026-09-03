import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recorder import record


def test_record_line_shape():
    buf = io.StringIO()
    record("deploy", "web-farm is live", buf)
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} deploy web-farm is live\n",
        buf.getvalue(),
    )
