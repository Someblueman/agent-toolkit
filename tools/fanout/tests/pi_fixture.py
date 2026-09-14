"""Native-shaped Pi fixture for CLI and failure boundary tests."""

import sys
import textwrap
from pathlib import Path


def create_fake_pi(path: Path) -> Path:
    path.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent("""\
        import json
        import os
        import re
        import sys
        import time
        from pathlib import Path
        args = sys.argv[1:]
        assert args[:4] == ['--mode', 'json', '--print', '--no-session']
        assert '--approve' not in args and '--no-extensions' not in args
        assert sys.stdin.read() == ''
        assert args[-2] == '--' and args[-1].startswith('@')
        prompt = Path(args[-1][1:])
        (prompt.parent / 'invocation.json').write_text(json.dumps(args))
        worker = re.search(r'worker-\\d{4}', prompt.read_text()).group()
        mode = os.environ.get('PI_TEST_MODE', 'success')
        if mode == 'hang':
            time.sleep(60)
        if mode == 'nonzero':
            sys.exit(7)
        if mode == 'oversized':
            print('x' * 10000)
            sys.exit(0)
        result = {'worker_id': worker, 'outcome': 'blocked' if mode == 'partial' and worker == 'worker-0002' else 'completed', 'summary': 'Reviewed', 'result_json': '{"answer":42}'}
        text = 'not json' if mode == 'malformed' else json.dumps(result)
        message = {'role': 'assistant', 'stopReason': 'stop', 'content': [{'type': 'text', 'text': text}], 'usage': {'totalTokens': 42, 'cost': {'total': 0.01}}}
        print(json.dumps({'type': 'message_end', 'message': message}))
        if mode != 'incomplete':
            print(json.dumps({'type': 'agent_end', 'messages': [message], 'willRetry': False}))
    """)
    )
    path.chmod(0o755)
    return path
