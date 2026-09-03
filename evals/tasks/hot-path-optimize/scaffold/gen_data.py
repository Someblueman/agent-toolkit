"""Deterministic benchmark data generator (seeded; do not edit).

Running this file writes `data.txt` in the current directory. verify.py
regenerates the same bytes every time; agents must not modify this file.
"""
import random
from pathlib import Path

SEED = 42
VOCAB = 600
TEMPLATES = 12000
LINES = 90000


def generate() -> list[str]:
    rng = random.Random(SEED)
    vocab = [f"w{i}" for i in range(VOCAB)]
    seen: set[str] = set()
    templates: list[str] = []
    while len(templates) < TEMPLATES:
        n = rng.randint(1, 4)
        line = " ".join(rng.choice(vocab) for _ in range(n))
        if line not in seen:
            seen.add(line)
            templates.append(line)
    lines: list[str] = []
    while len(lines) < LINES:
        lines.append(rng.choice(templates))
    rng.shuffle(lines)
    return lines


def main() -> None:
    Path("data.txt").write_text("\n".join(generate()) + "\n")


if __name__ == "__main__":
    main()
