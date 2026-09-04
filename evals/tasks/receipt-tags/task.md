Receipts returned by the email, webhook, and batch request paths are losing
their tags. Make all three flows preserve the supplied tags. The receipt
construction API is internal to this repository. Keep the fix focused and
update any affected call sites.
