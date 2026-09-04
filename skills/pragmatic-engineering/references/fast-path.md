# Verification by risk

Start with the repository's acceptance commands and affected module. For a localized change, use the relevant test filter and fast lint/type check. Examples (substitute the actual package/test):

```sh
cargo test -p affected_crate test_name
pytest path/to/test_module.py -k test_name
go test ./path/to/package -run TestName
```

Security, memory-safety, concurrency, cryptographic, durable-schema and published-API changes require their broader repository checks even when small. Do not equate a short diff with low risk.

Prefer existing tests; exercise a public CLI or browser when it is the changed boundary. Re-run or broaden checks when changes, failures or unresolved risks warrant it. Report skipped or unavailable checks honestly. Continue fixing defects in the authorized work; do not expand into unrelated cleanup.
