# Algebraic Laws, Numeric Domains, and Property Testing

Use this page for law-bearing APIs, numeric or symbolic code, instances, normalization, and high-assurance property tests.

## Specify the Algebra Before the Representation

Record five things before implementation:

1. the carrier: which values are in the domain;
2. the equality used by laws: representation equality, normalized equality, denotation, or approximation;
3. the operations, including every partial operation and precondition;
4. the laws and any side conditions;
5. the evidence level: examples, executable properties, finite exhaustion, model comparison, or an external proof.

QuickCheck, unit tests, and typeclass instances provide useful executable evidence. They do not prove a law for all values. State claim ceilings honestly.

For quotient or normalized representations, prove or test the missing well-definedness obligations explicitly:

- every operation is a congruence: equivalent inputs produce equivalent outputs;
- partial-operation preconditions are invariant under the equivalence relation;
- normalization terminates, is idempotent, preserves denotation, and produces a unique canonical form if representation equality is exposed;
- `Eq`, `Ord`, hashing, display, serialization, and ordered/map/set-key behavior agree with the chosen equality or clearly advertise a different contract.

## Common Class Obligations

Check the laws actually used by clients, including superclass consistency:

| Class | Core obligations to consider |
| --- | --- |
| `Eq` | reflexive, symmetric, transitive; `x /= y` agrees with `not (x == y)` on the intended carrier |
| `Ord` | comparability, reflexivity, antisymmetry, and transitivity on the carrier; `compare x y == EQ` exactly when `x == y`; relational methods and `min`/`max` agree with the documented comparison semantics |
| `Semigroup` | associativity under the declared equality and domain; state whether the law excludes bottoms or observes strictness |
| `Monoid` | semigroup associativity plus left and right identity; confirm the empty value belongs to the carrier and normalization preserves the laws |
| `Functor` | identity and composition |
| `Applicative` | identity, composition, homomorphism, interchange; consistency with `Functor` |
| `Monad` | left identity, right identity, associativity; consistency with `Applicative` where expected |
| `Foldable` | `foldr`/`foldMap` and strict folds agree as documented in value and strictness; visit the intended fields/order; state behavior on infinite structures |
| `Traversable` | naturality, identity, composition; consistency with `Functor` and `Foldable` |

The `base` API documentation is authoritative for current class definitions and documented laws. Add domain-specific laws such as normalization idempotence, homomorphisms, involutions, round trips, conservation, or order compatibility explicitly.

## Numeric Semantics

- A `Num` constraint does not establish a mathematical ring. It permits domains with overflow, rounding, nonstandard equality, or operations that lack the laws your algorithm needs.
- Use a domain-specific class or a well-established algebra library only when its laws and dependency cost match the project. Do not invent a hierarchy solely for aesthetic generality.
- `Int` and `Word` are bounded. Under GHC, ordinary overflow is unchecked and uses the target representation's modular behavior; do not rely on it without a stated compiler/target contract. Specify checked, saturating, or modular behavior explicitly, separately from division-by-zero and conversion semantics. `Integer` is unbounded but can be expensive.
- `Float` and `Double` include rounding, infinities, signed zero, and NaN. Ordinary equality is not an approximate metric, and familiar laws such as associativity can fail.
- Do not use ordinary `Float`/`Double` keys in `Map`, `Set`, ordered indexes, or algorithms requiring a total order when NaN is in the carrier. Use a documented total-order wrapper or exclude/validate non-orderable values.
- Put tolerance in an explicit comparison operation with documented absolute/relative behavior. Do not hide approximate equality in a surprising `Eq` instance.
- Specify division by zero, negative exponents, modular reduction convention, overflow, underflow, conversions, and rounding.
- If multiple representations denote the same value, define a canonical form or an explicit denotational equality. Test normalization idempotence and preservation of meaning.
- Monomorphize numeric properties so defaulting cannot silently test a different domain.

## Instances and Deriving

- Use explicit deriving strategies (`stock`, `newtype`, `anyclass`, `via`) when more than one interpretation is plausible.
- Check derived `Eq` and `Ord` semantics against constructor and field order. Representation order is often not domain order.
- Treat `Show` as diagnostic unless a stable format is explicitly specified. Do not use derived `Show`/`Read` or `Generic` serialization as an accidental wire contract.
- With `GeneralizedNewtypeDeriving` or `DerivingVia`, confirm that representation reuse preserves the domain invariant and intended laws.
- For indexed quantities or units, review which operations are meaningful and what their result indices must be. Role safety alone does not make a derived `Num`, `Fractional`, `Ord`, or similar instance lawful.
- Review minimal complete definitions and defaults; mutually recursive defaults can compile and diverge.
- Avoid orphan, incoherent, or broadly overlapping instances unless the coherence tradeoff is deliberate and documented.

## Property-Test Design

- Name the domain, equality, preconditions, and observation depth for each property.
- Generate valid structured values directly. Heavy filtering can produce vacuous tests and poor shrinking.
- Write shrinkers that preserve validity, or normalize after shrinking only when that matches the semantics.
- Define explicit coverage obligations for every material constructor, exceptional branch, boundary, and partial-operation domain. Use `cover`/`coverTable` plus `checkCoverage` to make those obligations fail when unmet; `classify` and `collect` are diagnostics only.
- Do not accept an algebraic property merely because it reports successes. It must demonstrate non-vacuous coverage or be replaced/supplemented by exhaustive or model-based evidence.
- Add boundary values and invalid inputs deliberately. Random generators rarely discover every semantic edge.
- Compare with a small independent model or exhaust a finite domain when feasible.
- Test normalization, representation/denotation agreement, homomorphisms, inverses, round trips, and interaction laws—not just individual functions.
- For function-valued or infinite structures, test finite observable behavior and state the observation limit.
- Force results to the depth promised by the API so bottoms or exceptions are not hidden in unevaluated fields.
- Preserve the replay seed and minimized counterexample from important failures.

## Partial Algebraic Operations

Choose the API from the semantics rather than hiding a precondition:

- Use a restricted input type when callers can construct evidence of the valid domain and the restriction composes well.
- Use `Maybe` when only success/absence matters; use `Either DomainError` when failure distinctions guide recovery.
- Use a class whose operation is partial only when partiality is intrinsic, its domain is documented, and every law carries the necessary side condition.
- Totalize with an absorbing/error element only when that element is genuinely part of the intended algebra and all downstream laws include it.

For inverse, division, cancellation, and exponentiation, name the lawful subset—such as nonzero elements, units, or a cancellative carrier—and ensure generators and shrinkers stay inside it.

## Algebraic API Review

Before accepting an algebraic abstraction, answer:

1. What values are included and excluded?
2. What notion of equality appears in each law?
3. Are any operations partial or only conditionally lawful?
4. Do instances agree with each other and with normalization?
5. Can representation reuse through deriving or `coerce` bypass an invariant?
6. Which claims are tested, which are mechanically proved elsewhere, and which remain assumptions?
