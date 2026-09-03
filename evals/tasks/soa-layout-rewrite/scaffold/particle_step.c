/* Field simulation kernel.
 *
 * A world holds N particles; each particle carries a field value `x` that
 * evolves over time. One call to step() advances the field once. The fixed
 * harness in this file initializes the world from a deterministic seed,
 * runs warmup + timed steps, and prints a checksum of the field plus the
 * measured time per step:
 *
 *   cc -O3 particle_step.c && ./a.out [n] [seed]
 *
 * Improve the implementation so the reported time per step drops as much
 * as possible while every printed value stays bit-identical on any input.
 *
 * The region between HARNESS BEGIN and HARNESS END is checked byte-for-byte
 * by the scorer and must not change.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

/* One particle in the field. */
struct Particle {
    float x;       /* field value */
    float vx;      /* rate of change of the field */
    float y;
    float vy;
    float z;
    float vz;
    float mass;
    float charge;
};

enum { F_X, F_VX, F_Y, F_VY, F_Z, F_VZ, F_MASS, F_CHARGE };

/* The world owns all particle state for the run. */
struct World {
    size_t n;
    struct Particle *p;
};

struct World *world_create(size_t n);
void world_destroy(struct World *w);
void world_set(struct World *w, size_t i, int field, double v);
double world_get_x(const struct World *w, size_t i);
void step(struct World *w, float dt);

/* ===================== implementation ===================== */

struct World *world_create(size_t n) {
    struct World *w = malloc(sizeof *w);
    if (!w) abort();
    w->n = n;
    w->p = calloc(n, sizeof *w->p);
    if (!w->p) abort();
    return w;
}

void world_destroy(struct World *w) {
    free(w->p);
    free(w);
}

void world_set(struct World *w, size_t i, int field, double v) {
    struct Particle *p = &w->p[i];
    switch (field) {
    case F_X:     p->x = (float)v; break;
    case F_VX:    p->vx = (float)v; break;
    case F_Y:     p->y = (float)v; break;
    case F_VY:    p->vy = (float)v; break;
    case F_Z:     p->z = (float)v; break;
    case F_VZ:    p->vz = (float)v; break;
    case F_MASS:  p->mass = (float)v; break;
    case F_CHARGE: p->charge = (float)v; break;
    }
}

double world_get_x(const struct World *w, size_t i) {
    return (double)w->p[i].x;
}

void step(struct World *w, float dt) {
    const size_t n = w->n;
    for (size_t i = 0; i < n; i++) {
        w->p[i].x += w->p[i].vx * dt;
    }
}

/* ==== harness begin (do not modify) ==== */
#undef step
#undef world_create
#undef world_destroy
#undef world_set
#undef world_get_x
#undef clock_gettime
#undef printf
#undef mix64

static uint64_t mix64(uint64_t k) {
    k += 0x9E3779B97F4A7C15ULL;
    k = (k ^ (k >> 30)) * 0xBF58476D1CE4E5B9ULL;
    k = (k ^ (k >> 27)) * 0x94D049BB133111EBULL;
    return k ^ (k >> 31);
}

#define REPS 20

int main(int argc, char **argv) {
    size_t n = argc > 1 ? strtoull(argv[1], NULL, 10) : 2000000;
    uint64_t seed = argc > 2 ? strtoull(argv[2], NULL, 10) : 7;

    struct World *w = world_create(n);
    for (size_t i = 0; i < n; i++) {
        for (int f = 0; f < 8; f++) {
            uint64_t r = mix64(seed + (uint64_t)i * 1000003ULL + (uint64_t)f * 7919ULL);
            world_set(w, i, f, (double)(r >> 11) * (1.0 / 9007199254740992.0));
        }
    }

    const float dt = 0.0075f;
    for (int r = 0; r < 2; r++) step(w, dt); /* warmup */

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int r = 0; r < REPS; r++) step(w, dt);
    clock_gettime(CLOCK_MONOTONIC, &t1);

    double checksum = 0.0;
    for (size_t i = 0; i < n; i++) checksum += world_get_x(w, i);

    double ns = (double)(t1.tv_sec - t0.tv_sec) * 1e9
              + (double)(t1.tv_nsec - t0.tv_nsec);
    printf("checksum %.17g\n", checksum);
    printf("time_per_step_ms %.6f\n", ns / 1e6 / REPS);
    world_destroy(w);
    return 0;
}
/* ==== harness end ==== */
