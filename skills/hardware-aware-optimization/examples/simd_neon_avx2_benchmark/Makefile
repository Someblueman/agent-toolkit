CC ?= clang
CFLAGS ?= -O3 -Wall -Wextra -std=c11

all: simd_bench

simd_bench: simd_bench.c
	$(CC) $(CFLAGS) -march=native simd_bench.c -o simd_bench -lm

run: simd_bench
	./simd_bench

clean:
	rm -f simd_bench

.PHONY: all run clean
