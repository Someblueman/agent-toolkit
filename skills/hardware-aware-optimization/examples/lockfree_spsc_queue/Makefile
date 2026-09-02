CXX ?= clang++
CXXFLAGS ?= -O3 -Wall -Wextra -std=c++17 -pthread

all: spsc_bench

spsc_bench: spsc_bench.cpp
	$(CXX) $(CXXFLAGS) -march=native spsc_bench.cpp -o spsc_bench

run: spsc_bench
	./spsc_bench

clean:
	rm -f spsc_bench

.PHONY: all run clean
