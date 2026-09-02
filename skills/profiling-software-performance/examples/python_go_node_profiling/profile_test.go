package main

import (
	"testing"
)

var sink []int
var sinkInt int

func BenchmarkComputePrimes(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkInt = ComputePrimes(1000)
	}
}

func BenchmarkProcessDataHeap(b *testing.B) {
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sink = ProcessDataHeap(1000)
	}
}

func BenchmarkProcessDataPreallocated(b *testing.B) {
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sink = ProcessDataStack(1000)
	}
}

func TestParity(t *testing.T) {
	h := ProcessDataHeap(500)
	s := ProcessDataStack(500)
	if len(h) != len(s) {
		t.Fatalf("Length mismatch: %d != %d", len(h), len(s))
	}
	for i := range h {
		if h[i] != s[i] {
			t.Fatalf("Value mismatch at %d: %d != %d", i, h[i], s[i])
		}
	}
}
