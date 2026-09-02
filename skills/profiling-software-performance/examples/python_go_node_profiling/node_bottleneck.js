/**
 * Node.js / V8 Profiling Benchmark Demo: CPU vs Object Churn.
 *
 * Demonstrates:
 * 1. CPU-bound prime searching.
 * 2. Object allocation churn (creating millions of intermediate objects) vs flat typed array.
 * 3. Parity verification between object and buffer implementations.
 */

const assert = require('assert');

// 1. CPU Bottleneck: Prime Calculation
function computePrimes(limit) {
    let count = 0;
    for (let i = 2; i < limit; i++) {
        let isPrime = true;
        const sqrt = Math.floor(Math.sqrt(i));
        for (let j = 2; j <= sqrt; j++) {
            if (i % j === 0) {
                isPrime = false;
                break;
            }
        }
        if (isPrime) count++;
    }
    return count;
}

// 2. Memory Allocation Bottleneck: Creating millions of temporary small objects
function processWithObjectChurn(n) {
    let totalSum = 0;
    for (let i = 0; i < n; i++) {
        // High heap allocation churn: V8 hidden class instantiation per iteration
        const obj = { id: i, value: i * 2, label: `item_${i}` };
        totalSum += obj.value;
    }
    return totalSum;
}

// 3. Memory Efficient: Flat typed array / scalar calculation
function processEfficient(n) {
    let totalSum = 0;
    for (let i = 0; i < n; i++) {
        totalSum += i * 2;
    }
    return totalSum;
}

function main() {
    console.log('=== Node.js / V8 Runtime Profiling Demo ===\n');

    // 1. Parity Check
    const sumA = processWithObjectChurn(100000);
    const sumB = processEfficient(100000);
    assert.strictEqual(sumA, sumB, `Parity check failed: ${sumA} !== ${sumB}`);
    console.log('[+] Parity Check PASSED: Object churn and efficient loops produce identical sums.');

    // 2. Measure CPU Workload
    console.time('CPU Primes Workload (100k)');
    const primes = computePrimes(100000);
    console.timeEnd('CPU Primes Workload (100k)');
    console.log(`    Found ${primes} primes.`);

    // 3. Measure Object Churn vs Efficient
    console.time('Object Churn (5M objects)');
    processWithObjectChurn(5000000);
    console.timeEnd('Object Churn (5M objects)');

    console.time('Scalar Loop (5M iterations)');
    processEfficient(5000000);
    console.timeEnd('Scalar Loop (5M iterations)');

    console.log('\nProfiling instructions:');
    console.log('  1. CPU tick profile: node --prof node_bottleneck.js && node --prof-process isolate-*.log');
    console.log('  2. V8 CPU profile:   node --cpu-prof node_bottleneck.js');
    console.log('  3. V8 Heap profile:  node --heap-prof node_bottleneck.js');
}

if (require.main === module) {
    main();
}
