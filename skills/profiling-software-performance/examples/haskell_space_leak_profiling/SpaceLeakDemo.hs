{-# LANGUAGE BangPatterns #-}
module Main where

import System.Environment (getArgs)
import Data.List (foldl')
import Control.Exception (assert)

-- 1. Space Leak: Lazy left fold accumulating unevaluated thunks
-- 'foldl' builds a chain of unevaluated thunk expressions:
-- (((0 + 1) + 2) + 3) ... + N
-- This causes O(N) heap allocation and high GC traversal pressure.
sumLazyFold :: [Int] -> Int
sumLazyFold = foldl (+) 0

-- 2. Strict Accumulator: Forcing evaluation of accumulator to WHNF at each step
-- Evaluates accumulator immediately using strict 'foldl'', requiring O(1) constant heap space.
sumStrictFold :: [Int] -> Int
sumStrictFold = foldl' (+) 0

-- 3. Recursive Worker with BangPattern for explicit WHNF strictness
sumStrictWorker :: [Int] -> Int
sumStrictWorker xs = go 0 xs
  where
    go !acc []     = acc
    go !acc (y:ys) = go (acc + y) ys

main :: IO ()
main = do
    args <- getArgs
    let n = case args of
              (x:_) -> read x :: Int
              []    -> 500000

    putStrLn "=== Haskell GHC Profiling: Space Leak vs Strict Accumulator ==="
    putStrLn $ "Processing list [1.." ++ show n ++ "]..."

    -- Parity Check
    let testList = [1..10000]
        sumL = sumLazyFold testList
        sumS = sumStrictFold testList
        sumW = sumStrictWorker testList

    if sumL == sumS && sumS == sumW
      then putStrLn "[PASS] Parity verified: All fold implementations produce identical sums."
      else error "Parity failure: Mathematical results diverged!"

    -- Workload evaluation
    let targetList = [1..n]
    putStrLn "\nEvaluating Lazy Fold (accumulates thunks)..."
    let !resLazy = {-# SCC "sumLazy" #-} sumLazyFold targetList
    putStrLn $ "  Lazy Sum Result: " ++ show resLazy

    putStrLn "\nEvaluating Strict Fold (O(1) heap space)..."
    let !resStrict = {-# SCC "sumStrict" #-} sumStrictFold targetList
    putStrLn $ "  Strict Sum Result: " ++ show resStrict

    putStrLn "\nEvaluating BangPattern Worker..."
    let !resWorker = {-# SCC "sumWorker" #-} sumStrictWorker targetList
    putStrLn $ "  Worker Sum Result: " ++ show resWorker

    putStrLn "\n[+] Execution complete. Run with '+RTS -p -s' to inspect cost-centre time and GC statistics."
