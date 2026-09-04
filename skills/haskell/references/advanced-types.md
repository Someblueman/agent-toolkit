# Advanced Types, Roles, and Compile-Time Contracts

Use this page for GADTs, `DataKinds`, type families, nontrivial constraints, deriving machinery, or APIs whose safety depends on `Coercible`.

## Choose the Lightest Mechanism

- Prefer a runtime ADT and smart constructor when it expresses the requirement clearly enough.
- Use advanced type features when they materially remove invalid programs or clarify eliminators, not merely to move ordinary branching into harder error messages.
- Make kinds and important signatures explicit at public boundaries.
- A type-level invariant constrains values built through the checked API. It does not validate FFI input, deserialization, `unsafeCoerce`, or hidden bottoms.
- Preserve the repository's supported GHC versions before selecting an extension or syntax.

## GADTs and Existentials

- State what evidence each constructor introduces and which operations may consume it.
- Keep elimination sites small and explicit. Pattern matching is where GADT refinements become available.
- Give eliminators explicit signatures; GHC's refinement depends on user-supplied type information, and named proofs may require scoped type variables.
- For existential packages, expose only observations that are valid for every hidden type, or store the exact dictionaries required by those observations.
- Test construction and elimination at runtime, and add compile-fail cases showing that forbidden combinations remain rejected.
- If values cross a serialization boundary, validate the runtime tag before reconstructing typed evidence.

## Data Kinds and Type Families

- Distinguish open families, whose equations may be extended, from closed families, whose ordered equations define a sealed reduction strategy.
- Account for stuck reductions. A type family application need not reduce merely because a human expects a unique answer.
- Do not assume a family is injective or generative unless the declaration and compiler rules establish that property.
- Review family arity and saturation constraints when passing type-level functions around.
- Treat `UndecidableInstances` as an obligation to supply your own termination/coherence argument, not a harmless spelling fix.
- Review overlaps between equations and the public consequences of open extension.
- Quantified constraints, functional dependencies, and injective families are API commitments. Document the inference behavior callers depend on.

## Roles and `Coercible`

GHC assigns each parameter a role:

| Role | What representation coercion may assume |
| --- | --- |
| nominal | the argument types must be nominally equal |
| representational | their runtime representations may be coerced |
| phantom | the argument does not affect representation |

- Inspect inferred roles for abstract types whose parameter carries units, ordering, normalization, permissions, ownership, or another semantic invariant.
- Add a nominal role annotation when representational coercion would let callers change meaning while preserving bits.
- Constructor hiding alone does not prevent every `coerce`-based conversion.
- `Coercible` proves a representation relationship, not a domain law.
- Re-check roles after changing fields, type families, or class constraints.
- Apply the same semantic review to `GeneralizedNewtypeDeriving` and `DerivingVia`.

## Classes, Constraints, and Coherence

- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- **Records of Functions over Speculative Typeclasses**: Prefer passing concrete records of functions (`data UserRepo = UserRepo { findUser :: UserId -> IO (Maybe User) }`) over typeclass dictionaries or multi-parameter typeclasses with functional dependencies. Records are simple, inspectable, and mockable without complex type-level machinery.
- **Monad Simplicity over Effect Abstraction**: Ban speculative custom monad transformer stacks (`ReaderT C (ExceptT E (StateT S IO))`) and extensible effect frameworks (Polysemy, Freer, Eff) for standard application code. Default to concrete `ReaderT Env IO` or plain functions with explicit environment parameters.
- Keep constraints no stronger than needed, but do not conceal essential laws behind a weak standard class.
- Review orphan, overlapping, incoherent, and recursive instances as whole-program coherence decisions.
- Use explicit deriving strategies when compiler choice could change semantics.
- Check default methods for accidental recursive loops and ensure the minimal complete definition matches the intended implementation burden.

## Verification

For an advanced type-level API, include as appropriate:

- positive compile tests for intended use;
- negative compile tests for forbidden use, scoped to stable diagnostic fragments or success/failure rather than brittle full messages;
- runtime tests for singleton/demotion or existential eliminators;
- law tests for every runtime operation hidden behind the types;
- tests showing abstract constructors, roles, and coercions cannot bypass invariants;
- the supported GHC matrix when behavior depends on inference, solver, roles, or extensions.

A rejected sample establishes only that the particular sample is rejected under the tested compiler and flags. It is not a global proof that every invalid program is unrepresentable.
