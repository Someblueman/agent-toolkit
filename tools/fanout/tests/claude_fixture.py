"""Native-shaped Claude Code subprocess fixture."""

import sys
import textwrap
from pathlib import Path


def create_fake_claude(path: Path) -> Path:
    path.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent("""\
        import json
        import os
        import sys
        import time
        from pathlib import Path
        args = sys.argv[1:]
        assert args[:4] == ['--print', '--output-format', 'json', '--no-session-persistence']
        assert not any(flag in args for flag in ['--dangerously-skip-permissions', '--permission-mode', '--allowedTools', '--bare', '--continue', '--resume'])
        schema = json.loads(args[args.index('--json-schema') + 1])
        worker = schema['properties']['worker_id']['const']
        prompt = sys.stdin.read()
        assert worker in prompt and 'Fan-out response contract' in prompt
        mode = os.environ.get('CLAUDE_TEST_MODE', 'success')
        if mode == 'hang':
            time.sleep(60)
        if mode == 'nonzero':
            sys.exit(7)
        if mode == 'oversized':
            print('x' * 10000)
            sys.exit(0)
        if mode == 'malformed':
            print('not json')
            sys.exit(0)
        receipt = {'worker_id': worker, 'outcome': 'blocked' if mode == 'partial' and worker == 'worker-0002' else 'completed', 'summary': 'Reviewed', 'result_json': json.dumps({'model': args[args.index('--model') + 1] if '--model' in args else None, 'cwd': str(Path.cwd()), 'prompt': prompt})}
        print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': receipt, 'usage': {'input_tokens': 10, 'output_tokens': 12, 'cache_creation_input_tokens': 5, 'cache_read_input_tokens': 15}, 'total_cost_usd': 0.01}))
    """)
    )
    path.chmod(0o755)
    return path
