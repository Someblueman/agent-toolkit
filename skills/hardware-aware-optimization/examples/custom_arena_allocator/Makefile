CXX ?= clang++
CXXFLAGS ?= -O3 -Wall -Wextra -std=c++17

all: arena_bench

arena_bench: arena_bench.cpp
	$(CXX) $(CXXFLAGS) -march=native arena_bench.cpp -o arena_bench

run: arena_bench
	./arena_bench

clean:
	rm -f arena_bench

.PHONY: all run clean
