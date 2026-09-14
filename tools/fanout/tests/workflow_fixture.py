"""Shared native-protocol subprocess fixture for workflow boundary tests."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from fixtures import FANOUT_BIN, load_fanout_module

load_fanout_module()


class WorkflowCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.prompt = self.root / "request.md"
        self.prompt.write_text("Inspect the target using the supplied constraints.")
        self.config = self.root / "config.json"
        self.output = self.root / "output"
        self.events = self.root / "events.jsonl"
        self.executables = {}
        for harness in ("pi", "claude", "agy", "muse"):
            executable = self.root / harness
            executable.write_text(
                f"#!{sys.executable}\n"
                + textwrap.dedent("""\
                import json, os, re, sys, time, subprocess
                from pathlib import Path
                args = sys.argv[1:]
                harness = Path(sys.argv[0]).name
                model = args[args.index('--model') + 1]
                if harness == 'pi':
                    prompt = Path(args[-1][1:]).read_text()
                elif harness == 'agy':
                    prompt = next(a[len('--print='):] for a in args if a.startswith('--print='))
                    assert '--sandbox' in args and args[args.index('--mode')+1]=='plan'
                elif harness == 'muse':
                    prompt = Path(args[args.index('--prompt-file')+1]).read_text()
                else:
                    prompt = sys.stdin.read()
                    assert '--no-session-persistence' in args
                    assert '--permission-mode' not in args
                worker = re.search(r'Your (?:assigned )?worker_id is (worker-\\d{4})', prompt).group(1)
                event_path = Path(os.environ['WORKFLOW_EVENTS'])
                def event(kind):
                    with event_path.open('a') as f:
                        f.write(json.dumps({'kind':kind,'worker':worker,'model':model,'harness':harness,'time':time.monotonic(),'args':args,'effort':os.environ.get('CLAUDE_CODE_EFFORT_LEVEL')})+'\\n')
                event('start')
                if os.environ.get('WORKFLOW_BARRIER') and worker in ('worker-0001','worker-0002'):
                    deadline=time.monotonic()+3
                    while sum(json.loads(line)['kind']=='start' for line in event_path.read_text().splitlines()) < 2 and time.monotonic()<deadline:
                        time.sleep(0.01)
                time.sleep(0.1)
                if model == 'hang': time.sleep(60)
                if model == 'nonzero': sys.exit(7)
                assignment = json.JSONDecoder().raw_decode(prompt.split('Assignment: ',1)[1])[0]
                schema = json.JSONDecoder().raw_decode(prompt.split('For blocked/failed, explain why in summary and use {} for payload.\\n',1)[1])[0]
                payload = {key:[] for key in schema['required']}
                if 'owned_paths' in assignment:
                    owned = assignment['owned_paths'][0]
                    Path(owned).write_text('VALUE = 1\\n')
                    checks=[]
                    for command in assignment['acceptance']:
                        result=subprocess.run(command, shell=True, capture_output=True, text=True)
                        checks.append({'command':command,'status':'passed' if result.returncode==0 else 'failed','evidence':result.stdout or result.stderr or 'exit 0'})
                    payload={'changes':[owned], 'checks':checks, 'blockers':[]}
                    subprocess.run(['git','add',owned],check=True)
                    subprocess.run(['git','commit','-m','owned change'],check=True,stdout=subprocess.DEVNULL)
                if model == 'outside': Path('outside.txt').write_text('unexpected')
                if model == 'mutate': Path('changed.txt').write_text('unexpected')
                if model == 'invalid': payload={'not':'the schema'}
                receipt={'worker_id':worker,'outcome':'blocked' if model=='blocked' else 'completed','summary':'Completed check','payload':payload}
                event('end')
                if harness=='pi':
                    message={'role':'assistant','provider':'fixture','model':model,'stopReason':'stop','content':[{'type':'text','text':json.dumps(receipt)}]}
                    print(json.dumps({'type':'message_end','message':message}))
                    print(json.dumps({'type':'agent_end','messages':[message]}))
                elif harness=='claude':
                    print(json.dumps({'type':'result','subtype':'success','is_error':False,'structured_output':receipt,'modelUsage':{model:{}}}))
                elif harness=='muse':
                    print(json.dumps({'schema_version':1,'payload_type':'runtime.command.accepted','payload':{'command_kind':'turn.submit','command_id':'root'}}))
                    print(json.dumps({'schema_version':1,'payload_type':'run.terminal.completed','payload':{'command_id':'root','terminal':'completed','text':json.dumps(receipt)}}))
                else:
                    print(json.dumps({'status':'SUCCESS','structured_output':receipt}))
            """)
            )
            executable.chmod(0o755)
            self.executables[harness] = executable

    def configure(self, members, workflow="review-plan"):
        data = {"version": 1, "workflows": {workflow: {"members": members}}}
        self.config.write_text(json.dumps(data))
        return data

    def run_workflow(self, workflow="review-plan", extra=(), env=None):
        command = [
            sys.executable,
            str(FANOUT_BIN),
            str(self.prompt),
            "--workflow",
            workflow,
            "--config",
            str(self.config),
            "--working-directory",
            str(self.cwd),
        ]
        if "--describe" not in extra:
            command += ["--output", str(self.output)]
        for harness, path in self.executables.items():
            command += ["--" + harness, str(path)]
        command += list(extra)
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env={**os.environ, "WORKFLOW_EVENTS": str(self.events), **(env or {})},
        )

    def packet(self):
        return json.loads((self.output / "packet.json").read_text())


def member(name, harness="pi", model=None, **kwargs):
    return {"id": name, "harness": harness, "model": model or name, **kwargs}
