{-# LANGUAGE BangPatterns #-}

module SimplifiedStrict (
    Stats(..),
    computeStatsStrict
) where

import BaselineLazy (Stats(..))

-- | Strict Worker-Wrapper transformation:
-- 1. Evaluates all accumulator components to Weak Head Normal Form (WHNF) eagerly.
-- 2. Uses BangPatterns (!cnt, !accS, !accSq) to prevent thunk chaining.
-- 3. Enables GHC to optimize loop into strict registers with zero heap allocations in the hot path.
computeStatsStrict :: [Double] -> Stats
computeStatsStrict xs = worker xs 0 0.0 0.0
  where
    -- Worker function with strict unboxed accumulators
    worker [] !cnt !accS !accSq =
        let mean = if cnt == 0 then 0.0 else accS / fromIntegral cnt
            variance = if cnt <= 1 then 0.0 else (accSq - (accS * accS) / fromIntegral cnt) / fromIntegral (cnt - 1)
        in Stats cnt accS mean variance
    worker (y:ys) !cnt !accS !accSq =
        worker ys (cnt + 1) (accS + y) (accSq + (y * y))
