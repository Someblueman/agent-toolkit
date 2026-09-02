package main

import (
	"fmt"
	"math"
)

// ProcessDataHeap creates dynamic heap slices causing allocation churn
func ProcessDataHeap(n int) []int {
	var result []int
	for i := 0; i < n; i++ {
		// Dynamic append causes repeated slice relocations on heap
		result = append(result, i*2)
	}
	return result
}

// ProcessDataStack pre-allocates buffer capacity to minimize heap re-allocations
func ProcessDataStack(n int) []int {
	result := make([]int, 0, n)
	for i := 0; i < n; i++ {
		result = append(result, i*2)
	}
	return result
}

// ComputePrimes performs CPU-bound computation
func ComputePrimes(limit int) int {
	count := 0
	for i := 2; i < limit; i++ {
		isPrime := true
		for j := 2; j <= int(math.Sqrt(float64(i))); j++ {
			if i%j == 0 {
				isPrime = false
				break
			}
		}
		if isPrime {
			count++
		}
	}
	return count
}

func main() {
	fmt.Println("=== Go Managed Profiling Demo ===")
	primes := ComputePrimes(10000)
	fmt.Printf("Primes up to 10,000: %d\n", primes)

	heapData := ProcessDataHeap(1000)
	stackData := ProcessDataStack(1000)

	// Parity verification
	if len(heapData) != len(stackData) {
		panic("Length mismatch")
	}
	for i := range heapData {
		if heapData[i] != stackData[i] {
			panic(fmt.Sprintf("Mismatch at index %d", i))
		}
	}
	fmt.Println("[+] Parity check passed: heap and stack implementations match.")
}
