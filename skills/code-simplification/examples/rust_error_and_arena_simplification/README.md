# Example: Rust Arena Index Graph & Error Simplification

## Problem Overview
Graph structures and self-referential models in Rust often lead to "lifetime fighting", overuse of `Rc<RefCell<Node>>`, memory cycle leaks, and runtime borrow-check panics. Additionally, manual `Error` implementations require excessive boilerplate.

## Refactoring Strategy
1. **Generational Arena Vector**: Store all nodes in a flat `Vec<ArenaNode>` and reference neighbors by lightweight copyable index handles (`NodeId(usize)`).
2. **Eliminate `Rc<RefCell>`**: Replace dynamic borrow checking and heap pointer chasing with direct array indexing.
3. **Unified Error Handling**: Replace manual `Display` + `Error` boilerplate with `#[derive(thiserror::Error)]`.

## Verification
```bash
cargo test
```
