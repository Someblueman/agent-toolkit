`particle_step.c` holds a small field-simulation kernel: `step()` advances
every particle's field value once per call (`x = x + vx*dt`), and the fixed
harness in the same file initializes a world from a deterministic seed, runs
warmup plus timed steps, and prints a checksum of the field together with the
measured time per step:

    cc -O3 particle_step.c && ./a.out [n] [seed]

The scorer compiles the file with `cc -O3` and runs it on large deterministic
datasets. It requires the reported time per step to be at least 3x lower than
the current implementation, with every printed value bit-identical on every
dataset it tests.

Constraints:
- Keep the declared API exactly as-is (`world_create`, `world_destroy`,
  `world_set`, `world_get_x`, `step`); the harness must keep compiling
  unmodified.
- The region between `harness begin` and `harness end` must remain
  byte-identical; the scorer rejects anything else.
- Results must be identical to the current build on any input — same bits,
  not approximately equal.
- The scorer uses `cc -O3` only; do not rely on extra compiler flags.
- Edit only `particle_step.c`. No external dependencies.
