# Haskell Optimization & GHC Internals

Haskell's default non-strict semantics evaluate expressions lazily, constructing unevaluated function closures (thunks) on the heap. While lazy evaluation provides composability and infinite structures, it introduces severe memory and CPU overhead in tight computational kernels due to pointer indirection, heap allocations, and garbage collection pressure.

By combining unboxed primitives (`Int#`, `ByteArray#`), strictness pragmas, record field unpacking, stream fusion, worker-wrapper transformations, and GHC rewrite rules, Haskell code can match the execution speed of optimized C.

---

## 1. Boxed vs. Unboxed Memory Representation

In standard Haskell, an `Int` is a boxed heap pointer pointing to a 2-word closure (Info Pointer + 64-bit integer value):

```
Standard Boxed Int (16–24 bytes on heap + pointer):
┌──────────────────────────┐
│  Ptr (8B) ───────────────┼───► ┌────────────────────┐
└──────────────────────────┘     │ Info Table Ptr (8B)│
                                 ├────────────────────┤
                                 │ Machine Int# (8B)  │
                                 └────────────────────┘

Unboxed Int# (8 bytes in CPU register!):
┌──────────────────────────┐
│  Machine Int# in Register│ (0 bytes heap, 0 GC overhead)
└──────────────────────────┘
```

---

## 2. Unboxed Primitives & `MagicHash`

Using the `MagicHash` language extension, programs can write low-level algorithms operating directly on CPU registers and raw memory buffers:

```haskell
{-# LANGUAGE MagicHash #-}
{-# LANGUAGE BangPatterns #-}
{-# LANGUAGE UnboxedTuples #-}

module FastMath where

import GHC.Exts

-- Pure unboxed worker: takes raw register Int# values, returns unboxed Int#
-- Zero heap allocations!
fastSumWorker :: Int# -> Int# -> Int#
fastSumWorker limit# = go 0# 0#
  where
    go !acc# !i#
      | isTrue# (i# >=# limit#) = acc#
      | otherwise               = go (acc# +# i#) (i# +# 1#)

-- Boxed public API wrapper
fastSum :: Int -> Int
fastSum (I# limit#) = I# (fastSumWorker limit#)
```

---

## 3. Strictness Enforcement & Record Unpacking (`{-# UNPACK #-}`)

### Record Unpacking
When a strict field is marked with `{-# UNPACK #-}`, GHC strips the boxed pointer wrapper and embeds the raw primitive bytes directly inside the parent constructor:

```haskell
{-# LANGUAGE BangPatterns #-}

-- BAD: Boxed fields introduce 2 pointer dereferences per point access
data BoxedPoint = BoxedPoint Double Double

-- OPTIMAL: UNPACK inlines 8-byte IEEE-754 floats directly into the Point constructor
data Point = Point
  {-# UNPACK #-} !Double
  {-# UNPACK #-} !Double

-- Distance calculation compiles to single-cycle scalar FPU / SIMD instructions
euclideanDistance :: Point -> Point -> Double
euclideanDistance (Point !x1 !y1) (Point !x2 !y2) =
  let !dx = x2 - x1
      !dy = y2 - y1
  in sqrt (dx * dx + dy * dy)
```

---

## 4. Stream Fusion with `Data.Vector.Unboxed`

Standard lists `[a]` allocate a cons cell `(:)` on the heap for every element. `Data.Vector.Unboxed` stores elements in flat byte arrays and uses stream fusion to collapse multi-stage pipelines (`filter`, `map`, `foldl'`) into a single non-allocating loop:

```haskell
import qualified Data.Vector.Unboxed as U

-- Inlined pipeline fuses into a single tight machine loop (0 intermediate vectors)
computeVectorPipeline :: U.Vector Double -> Double
computeVectorPipeline vec =
  U.foldl' (+) 0.0
    . U.map (\x -> x * 2.5 + 1.0)
    . U.filter (> 0.0)
    $ vec
```

### Inspecting Stream Fusion in GHC Core
Compile with Core dump flags to verify that all intermediate closures are eliminated:
```bash
ghc -O2 -ddump-simpl -dsuppress-all -dsuppress-uniques Pipeline.hs
```
If stream fusion succeeded, the output will contain a single recursive `$wfold` loop without constructor allocations.

---

## 5. Worker-Wrapper Transformations

GHC automatically applies the worker-wrapper transformation when `-O2` and `-fworker-wrapper` are enabled. It unboxes function arguments at the API boundary, performs all recursive iterations using unboxed registers, and boxes the final result once at the end:

```haskell
-- Source code:
fib :: Int -> Int
fib n = go n 0 1
  where
    go 0 a _ = a
    go m a b = go (m - 1) b (a + b)

-- GHC Generated Core (Worker-Wrapper):
-- $wgo :: Int# -> Int# -> Int# -> Int#   <-- Unboxed recursive worker
-- fib :: Int -> Int                      <-- Boxed wrapper calling $wgo
```

To assist the worker-wrapper pass on complex recursive functions, always ensure accumulators are strict (`!acc`) or explicitly unboxed (`Int#`).

---

## 6. GHC Rewrite Rules (`{-# RULES #-}`)

Rewrite rules allow library authors to define domain-specific compile-time optimizations:

```haskell
module CustomRules where

-- Custom function definitions
scale :: Double -> Double -> Double
scale !factor !x = factor * x
{-# INLINE [1] scale #-}

-- Algebraic Rewrite Rule: scale a (scale b x) ==> scale (a * b) x
{-# RULES
"scale/scale" forall a b x.
  scale a (scale b x) = scale (a * b) x
#-}
```

### Critical Rules for GHC Rewrite `RULES`:
1. **Phase Control**: Functions involved in rules MUST be marked `{-# INLINE [1] func #-}` or `{-# NOINLINE [1] func #-}`. If a function is inlined in Phase 2 or Phase 0 before rules run, the rule will never match.
2. **Verification**: Verify that rules fire using `-ddump-rule-firings` and `-ddump-rule-rewrites`:
   ```bash
   ghc -O2 -ddump-rule-firings Test.hs
   ```
   *Expected output*: `Rule fired: scale/scale`

---

## 7. Aggressive Monomorphization & Specialization

Polymorphic Haskell functions pass typeclass dictionaries (vtables) as hidden arguments, causing indirect function calls in hot loops.

```haskell
-- Specialized and inlined for concrete types
{-# SPECIALIZE sumList :: [Int] -> Int #-}
{-# SPECIALIZE sumList :: [Double] -> Double #-}

sumList :: Num a => [a] -> a
sumList = foldl' (+) 0
```

### Compiler Flags for Specialization:
- `-fspecialise-aggressively`: Tells GHC to specialize functions across module boundaries even when pragmas are absent.
- `-fexpose-all-unfoldings`: Exposes full function implementations to client modules for cross-module inlining.

---

## 8. GHC Optimization Inspection Flags Reference

| Command Flag | Purpose |
|---|---|
| `-ddump-simpl -dsuppress-all` | Inspect simplified System F Core (verify unboxing & fusion) |
| `-ddump-stg-final` | Inspect Spineless Tagless G-machine representation (verify closure allocation) |
| `-ddump-cmm` | Inspect low-level C-- intermediate representation |
| `-ddump-rule-firings` | List every GHC rewrite rule that successfully triggered |
| `+RTS -s` | Runtime memory allocation and GC statistics summary |
| `+RTS -p` | Runtime cost-centre profiling report (`.prof`) |
