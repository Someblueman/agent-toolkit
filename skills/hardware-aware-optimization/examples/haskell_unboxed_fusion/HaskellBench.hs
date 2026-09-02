{-# LANGUAGE BangPatterns #-}
{-# LANGUAGE MagicHash #-}
{-# LANGUAGE UnboxedTuples #-}
{-# LANGUAGE ScopedTypeVariables #-}
{-# LANGUAGE ExistentialQuantification #-}

{- |
  Haskell Optimization Benchmark:
  Boxed Lazy Lists vs Unboxed Worker-Wrapper & Stream Fusion
  ==========================================================
  Workload:
    Processes 10,000,000 numerical elements through a multi-stage pipeline:
      1. Generate values: x = i * 0.1
      2. Filter: x > 2.0
      3. Map: x * 1.5 + 0.5
      4. Fold: Sum accumulator
-}

module Main where

import GHC.Exts
import Data.List (foldl')
import Data.Time.Clock (getCurrentTime, diffUTCTime)
import Text.Printf (printf)

-- 1. Boxed Lazy List Baseline Pipeline
boxedPipeline :: Int -> Double
boxedPipeline n =
  foldl' (+) 0.0
    . map (\x -> x * 1.5 + 0.5)
    . filter (\x -> x > 2.0)
    $ [fromIntegral i * 0.1 | i <- [1..n]]

-- 2. Pure Unboxed Primitive Worker-Wrapper (MagicHash)
-- Operates strictly on Double# and Int# CPU registers. Zero Heap Allocations!
unboxedWorkerPipeline :: Int -> Double
unboxedWorkerPipeline (I# n#) = D# (go 0.0## 1#)
  where
    go :: Double# -> Int# -> Double#
    go !acc# !i#
      | isTrue# (i# ># n#) = acc#
      | otherwise =
          let !x# = int2Double# i# *## 0.1##
          in case x# >## 2.0## of
               1# ->
                 let !mapped# = (x# *## 1.5##) +## 0.5##
                 in go (acc# +## mapped#) (i# +# 1#)
               _  -> go acc# (i# +# 1#)

-- 3. High-Performance Fused Stream Pipeline
data Step s a = Done | Yield !a !s

data Stream a = forall s. Stream (s -> Step s a) !s

streamRange :: Int -> Int -> Stream Double
streamRange !start !end = Stream step start
  where
    step !i
      | i > end   = Done
      | otherwise = Yield (fromIntegral i * 0.1) (i + 1)
    {-# INLINE [0] step #-}
{-# INLINE [1] streamRange #-}

streamFilter :: (Double -> Bool) -> Stream Double -> Stream Double
streamFilter p (Stream step state) = Stream step' state
  where
    step' !s = case step s of
      Done -> Done
      Yield !x !s'
        | p x       -> Yield x s'
        | otherwise -> step' s'
    {-# INLINE [0] step' #-}
{-# INLINE [1] streamFilter #-}

streamMap :: (Double -> Double) -> Stream Double -> Stream Double
streamMap f (Stream step state) = Stream step' state
  where
    step' !s = case step s of
      Done -> Done
      Yield !x !s' -> Yield (f x) s'
    {-# INLINE [0] step' #-}
{-# INLINE [1] streamMap #-}

streamFold :: (Double -> Double -> Double) -> Double -> Stream Double -> Double
streamFold f !z0 (Stream step state) = loop z0 state
  where
    loop !acc !s = case step s of
      Done -> acc
      Yield !x !s' -> loop (f acc x) s'
    {-# INLINE [0] loop #-}
{-# INLINE [1] streamFold #-}

fusedStreamPipeline :: Int -> Double
fusedStreamPipeline !n =
  streamFold (+) 0.0
    . streamMap (\x -> x * 1.5 + 0.5)
    . streamFilter (> 2.0)
    $ streamRange 1 n
{-# INLINE fusedStreamPipeline #-}

timeAction :: String -> (Int -> Double) -> Int -> IO (Double, Double)
timeAction name fn n = do
  start <- getCurrentTime
  let !res = fn n
  end <- getCurrentTime
  let diffSec = realToFrac (diffUTCTime end start) :: Double
  let diffMs = diffSec * 1000.0
  printf "[*] %-28s Result = %16.4f | Time = %8.3f ms\n" name res diffMs
  return (res, diffMs)

main :: IO ()
main = do
  let n = 10000000 -- 10 Million elements
  putStrLn "==============================================================="
  putStrLn "   Haskell Optimization: Boxed vs Unboxed & Fusion     "
  putStrLn "==============================================================="
  printf "Pipeline Elements: %d\n\n" n

  -- 1. Run Boxed Baseline
  (resBoxed, tBoxed) <- timeAction "Boxed List Baseline" boxedPipeline n

  -- 2. Run Unboxed Worker-Wrapper (MagicHash)
  (resUnboxed, tUnboxed) <- timeAction "Unboxed Worker (MagicHash)" unboxedWorkerPipeline n

  -- 3. Run Fused Stream Pipeline
  (resFused, tFused) <- timeAction "Fused Stream Pipeline" fusedStreamPipeline n

  -- 4. Parity Verification
  putStrLn "\n[*] Verifying 100% Differential Parity..."
  let diff1 = abs (resBoxed - resUnboxed)
  let diff2 = abs (resBoxed - resFused)
  if diff1 > 1e-4 || diff2 > 1e-4
    then do
      putStrLn "[-] CRITICAL: Parity check failed between Haskell implementations!"
      error "Parity Mismatch"
    else putStrLn "[+] SUCCESS: 100% Parity Confirmed across all 10M elements!\n"

  -- 5. Benchmark Summary
  let speedupUnboxed = tBoxed / tUnboxed
  let speedupFused   = tBoxed / tFused

  putStrLn "==================== BENCHMARK RESULTS ===================="
  printf "Boxed List Time:            %8.3f ms\n" tBoxed
  printf "Unboxed Worker (MagicHash): %8.3f ms  (Speedup: %6.2fx)\n" tUnboxed speedupUnboxed
  printf "Fused Stream Pipeline:      %8.3f ms  (Speedup: %6.2fx)\n" tFused speedupFused
  putStrLn "==========================================================="
