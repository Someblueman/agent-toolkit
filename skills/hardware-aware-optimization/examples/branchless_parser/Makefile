CXX ?= clang++
CXXFLAGS ?= -O3 -Wall -Wextra -std=c++17

all: branchless_bench

branchless_bench: branchless_bench.cpp
	$(CXX) $(CXXFLAGS) -march=native branchless_bench.cpp -o branchless_bench

run: branchless_bench
	./branchless_bench

clean:
	rm -f branchless_bench

.PHONY: all run clean
