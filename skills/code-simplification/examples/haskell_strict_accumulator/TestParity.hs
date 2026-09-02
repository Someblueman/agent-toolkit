module Main where

import BaselineLazy (computeStatsLazy, Stats(..))
import SimplifiedStrict (computeStatsStrict)
import System.CPUTime (getCPUTime)
import System.Exit (exitFailure, exitSuccess)
import Text.Printf (printf)

-- | Deeply force Stats fields to WHNF
forceStats :: Stats -> ()
forceStats (Stats !c !s !m !v) = c `seq` s `seq` m `seq` v `seq` ()

-- | Numerical approximate equality check for floating point stats
statsApproxEq :: Stats -> Stats -> Double -> Bool
statsApproxEq (Stats c1 s1 m1 v1) (Stats c2 s2 m2 v2) tol =
    c1 == c2 &&
    abs (s1 - s2) <= tol &&
    abs (m1 - m2) <= tol &&
    abs (v1 - v2) <= tol

runEdgeCaseTests :: IO Bool
runEdgeCaseTests = do
    putStrLn "--- Running Edge Case Tests ---"
    let edge1 = [] :: [Double]
        edge2 = [42.0] :: [Double]
        edge3 = [10.0, 20.0, 30.0, 40.0, 50.0] :: [Double]
        edge4 = [-100.5, 0.0, 100.5, 200.25, -50.25] :: [Double]

    let pairs = [ (computeStatsLazy edge1, computeStatsStrict edge1)
                , (computeStatsLazy edge2, computeStatsStrict edge2)
                , (computeStatsLazy edge3, computeStatsStrict edge3)
                , (computeStatsLazy edge4, computeStatsStrict edge4)
                ]

    let allMatch = all (\(b, s) -> statsApproxEq b s 1e-7) pairs
    if allMatch
        then do
            putStrLn "✓ All deterministic edge cases match with 100% parity."
            return True
        else do
            putStrLn "❌ Edge case mismatch detected!"
            return False

runStreamBenchmark :: IO Bool
runStreamBenchmark = do
    putStrLn "--- Running Stream Parity & Benchmark (500,000 Elements) ---"
    let n = 500000 :: Int
        dataset = [1.0 .. fromIntegral n]

    -- Measure Baseline
    t0 <- getCPUTime
    let resLazy = computeStatsLazy dataset
    let !() = forceStats resLazy
    t1 <- getCPUTime
    let elapsedLazyMs = fromIntegral (t1 - t0) / (10^9 :: Double)

    -- Measure Simplified
    t2 <- getCPUTime
    let resStrict = computeStatsStrict dataset
    let !() = forceStats resStrict
    t3 <- getCPUTime
    let elapsedStrictMs = fromIntegral (t3 - t2) / (10^9 :: Double)

    let isMatch = statsApproxEq resLazy resStrict 1e-4
    printf "Baseline (Lazy)   : %s (Time: %.2f ms)\n" (show resLazy) elapsedLazyMs
    printf "Simplified (Strict): %s (Time: %.2f ms)\n" (show resStrict) elapsedStrictMs

    if isMatch
        then do
            let speedup = if elapsedStrictMs > 0 then elapsedLazyMs / elapsedStrictMs else 1.0
            printf "Speedup Ratio     : %.2fx faster\n" speedup
            putStrLn "✓ 500,000 element stream passed with 100% invariant parity."
            return True
        else do
            putStrLn "❌ Parity mismatch on stream evaluation!"
            return False

main :: IO ()
main = do
    putStrLn "================================================================="
    putStrLn " Running Haskell Strict Accumulator Parity & Benchmark Suite"
    putStrLn "================================================================="
    ok1 <- runEdgeCaseTests
    ok2 <- runStreamBenchmark
    putStrLn "================================================================="
    if ok1 && ok2
        then do
            putStrLn "Status: 100% Invariant Parity PASSED"
            exitSuccess
        else do
            putStrLn "Status: FAILED"
            exitFailure
