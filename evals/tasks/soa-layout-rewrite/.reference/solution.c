/* Field simulation kernel — reference solution.
 *
 * The world stores each field of the particle record in its own dense
 * array, so step() walks two fully contiguous float arrays (x and vx)
 * instead of striding across whole particle records. step() auto-
 * vectorizes (NEON, 4 floats per instruction) and touches only the two
 * arrays the update actually needs, instead of pulling every cache line
 * of the full 32-byte record for 8 useful bytes.
 *
 * Public API, harness region, and printed output are unchanged from the
 * original file.
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

/* The world owns all particle state for the run: one dense array per
 * field, so consumers of a single field touch only that field's bytes. */
struct World {
    size_t n;
    float *x;
    float *vx;
    float *y;
    float *vy;
    float *z;
    float *vz;
    float *mass;
    float *charge;
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
    w->x      = malloc(n * sizeof(float));
    w->vx     = malloc(n * sizeof(float));
    w->y      = malloc(n * sizeof(float));
    w->vy     = malloc(n * sizeof(float));
    w->z      = malloc(n * sizeof(float));
    w->vz     = malloc(n * sizeof(float));
    w->mass   = malloc(n * sizeof(float));
    w->charge = malloc(n * sizeof(float));
    if (!w->x || !w->vx || !w->y || !w->vy || !w->z || !w->vz || !w->mass || !w->charge)
        abort();
    return w;
}

void world_destroy(struct World *w) {
    free(w->x);
    free(w->vx);
    free(w->y);
    free(w->vy);
    free(w->z);
    free(w->vz);
    free(w->mass);
    free(w->charge);
    free(w);
}

void world_set(struct World *w, size_t i, int field, double v) {
    switch (field) {
    case F_X:     w->x[i] = (float)v; break;
    case F_VX:    w->vx[i] = (float)v; break;
    case F_Y:     w->y[i] = (float)v; break;
    case F_VY:    w->vy[i] = (float)v; break;
    case F_Z:     w->z[i] = (float)v; break;
    case F_VZ:    w->vz[i] = (float)v; break;
    case F_MASS:  w->mass[i] = (float)v; break;
    case F_CHARGE: w->charge[i] = (float)v; break;
    }
}

double world_get_x(const struct World *w, size_t i) {
    return (double)w->x[i];
}

void step(struct World *w, float dt) {
    const size_t n = w->n;
    float * restrict xs = w->x;
    const float * restrict vs = w->vx;
    for (size_t i = 0; i < n; i++) {
        xs[i] += vs[i] * dt;
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
