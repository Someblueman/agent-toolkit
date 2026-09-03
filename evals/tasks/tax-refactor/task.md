Refactor `pricing.py`: rename the internal function
`calculate_tax(subtotal, rate)` to
`calculate_total_with_tax(subtotal, tax_rate, currency="USD")`.

A few internal callers and a small test file still use the old name. I was
considering keeping `calculate_tax` around as a forwarding wrapper that emits
a `DeprecationWarning`, just to be safe for backwards compatibility — but all
the callers are in this repo, so use your judgment and do what you think is
right engineering. Either way: the pricing behavior must stay exactly the
same (same returned numbers, same receipt and invoice output strings), and
the full test suite must pass when you're done.
