"""Deterministic Muse CLI fixture using the observed native JSONL envelope."""

import sys
import textwrap
from pathlib import Path


def create_fake_muse(path: Path) -> Path:
    path.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent("""\
        import json
        import os
        import re
        import subprocess
        import sys
        import time
        from pathlib import Path

        args = sys.argv[1:]
        assert args[:2] == ['exec', '--json']
        assert '--no-session-log' in args
        assert not set(args) & {'--yolo', '--disable-approval', '--disable-sandbox', '--trust-workspace'}
        assert sys.stdin.read() == ''
        assert Path(args[args.index('--workspace') + 1]).resolve() == Path.cwd()
        prompt = Path(args[args.index('--prompt-file') + 1]).read_text()
        worker = re.search(r'worker-\\d{4}', prompt).group()
        mode = os.environ.get('MUSE_TEST_MODE', 'success')
        output = Path(args[args.index('--prompt-file') + 1]).parent
        (output / 'invocation.json').write_text(json.dumps(args))
        (output / 'start').write_text(str(time.monotonic()))
        if mode == 'hang':
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            (output / 'pids').write_text(f'{os.getpid()} {child.pid}')
            time.sleep(60)
        time.sleep(0.15)
        (output / 'end').write_text(str(time.monotonic()))
        if mode == 'nonzero':
            sys.exit(7)
        if mode == 'oversized':
            print('x' * 10000)
            sys.exit(0)
        def emit(kind, payload):
            print(json.dumps({'schema_version': 1, 'payload_type': kind, 'payload': payload}))
        emit('runtime.command.accepted', {'command_kind': 'turn.submit', 'command_id': worker})
        outcome = 'blocked' if mode == 'partial' and worker == 'worker-0002' else 'completed'
        receipt = {'worker_id': worker, 'outcome': outcome, 'summary': 'Read fixture', 'result_json': '{"evidence": "fixture"}'}
        if mode == 'wrong_id':
            receipt['worker_id'] = 'worker-9999'
        text = 'not json' if mode == 'malformed' else json.dumps(receipt)
        if mode != 'missing_terminal':
            emit('run.terminal.completed', {'command_id': worker, 'terminal': 'completed', 'text': text})
    """)
    )
    path.chmod(0o755)
    return path
