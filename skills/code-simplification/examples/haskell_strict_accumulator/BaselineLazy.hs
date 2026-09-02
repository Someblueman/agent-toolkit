module BaselineLazy (
    Stats(..),
    computeStatsLazy
) where

-- | Result statistics record
data Stats = Stats
    { statCount :: Int
    , statSum   :: Double
    , statMean  :: Double
    , statVar   :: Double
    } deriving (Show, Eq)

-- | Naive lazy accumulator creating thunk buildup in memory.
-- Does not evaluate intermediate arithmetic expressions, accumulating
-- lazy closures across the list traversal.
computeStatsLazy :: [Double] -> Stats
computeStatsLazy xs =
    let (n, s, sSq) = go xs (0, 0.0, 0.0)
        mean = if n == 0 then 0.0 else s / fromIntegral n
        variance = if n <= 1 then 0.0 else (sSq - (s * s) / fromIntegral n) / fromIntegral (n - 1)
    in Stats n s mean variance
  where
    go [] (cnt, accS, accSq) = (cnt, accS, accSq)
    go (y:ys) (cnt, accS, accSq) =
        -- Lazy tuple and arithmetic thunk allocations:
        go ys (cnt + 1, accS + y, accSq + (y * y))
