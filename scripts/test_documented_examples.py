"""Execute the documented cleanup and allocation examples at their failure boundaries."""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


class DocumentedExamples(unittest.TestCase):
    def test_cleanup_preserves_exit_and_signal_status(self):
        for name in ["bash-strict-modes.md", "shell-restraint-architecture.md"]:
            text = (SKILLS / "shell-engineering/references" / name).read_text()
            blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
            block = next(b for b in blocks if "cleanup() {" in b)
            # Execute the actual preamble, cleanup and trap setup, not the example's main.
            setup = block[
                : block.index("trap 'exit 129' HUP") + len("trap 'exit 129' HUP")
            ]
            for action, code in [
                ("exit 0", 0),
                ("exit 7", 7),
                ("kill -TERM $$", 143),
                ("kill -HUP $$", 129),
                ("kill -INT $$", 130),
            ]:
                with self.subTest(reference=name, action=action):
                    result = subprocess.run(
                        ["bash", "-c", setup + "\n" + action],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, code, result.stderr)

    @unittest.skipUnless(shutil.which("clang"), "clang unavailable")
    def test_c_arena_alignment_capacity_and_overflow(self):
        text = (SKILLS / "c-engineering/references/memory-arenas.md").read_text()
        blocks = re.findall(r"```c\n(.*?)```", text, re.DOTALL)
        block = next(b for b in blocks if "void *arena_alloc(" in b)
        assertions = r"""
#include <assert.h>
int main(void) {
    arena_t arena = {0};
    assert(arena_init(&arena, 128) == 0);
    assert(arena_alloc(&arena, 1, 3) == NULL);
    assert(arena_alloc(&arena, SIZE_MAX, 8) == NULL);
    assert(arena.offset == 0);
    unsigned char *p = arena_alloc(&arena, 8, 16);
    assert(p && (uintptr_t)p % 16 == 0);
    for (size_t i = 0; i < 8; ++i) assert(p[i] == 0);
    size_t offset = arena.offset;
    assert(arena_alloc(&arena, SIZE_MAX, 16) == NULL);
    assert(arena.offset == offset);
    arena_reset(&arena);
    assert(arena_alloc(&arena, 128, 1) != NULL);
    assert(arena_alloc(&arena, 1, 1) == NULL);
    arena_free(&arena);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as temp:
            source, binary = Path(temp) / "arena.c", Path(temp) / "arena"
            source.write_text(block + assertions)
            build = subprocess.run(
                [
                    "clang",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-fsanitize=undefined",
                    str(source),
                    "-o",
                    str(binary),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(binary)], capture_output=True, text=True, check=False, timeout=30
            )
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
