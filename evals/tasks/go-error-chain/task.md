# Region status board

`statusboard` is a three-layer service: the backend store (`FetchStatus`) talks
to a simulated region-status backend, `Service.CheckRegion` coordinates the
check, and `Handler.Handle` is the API-facing entry point.

An ops dashboard consumes `Handle`'s results. Two failure classes must be
programmatically distinguishable by every caller, no matter how many internal
layers the report travels through:

- **Region outage** — the caller must be able to detect it with
  `errors.Is(err, ErrRegionDown)`, and it must never be misreported as a
  backend failure.
- **Backend failure** — the caller must be able to extract the underlying
  `*BackendError` with `errors.As` (for the failing fixture regions that means
  `Code == 503` and `Endpoint == "status.internal.example.net"`, plus the
  node's own detail error), and it must never be misreported as a region
  outage.

Right now the dashboard can do neither classification. Fix
`Service.CheckRegion` and `Handler.Handle` so both classifications work end to
end.

Exact error text produced by `Handle` — callers match on these strings:

| fixture region | class           | exact error text                                                                                                                                                             |
|----------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `eu-west-1`    | outage          | `status probe for eu-west-1: checking region eu-west-1: fetching region status: region down`                                                                                   |
| `ap-south-1`   | outage          | `status probe for ap-south-1: checking region ap-south-1: fetching region status: region down`                                                                                 |
| `us-east-2`    | backend failure | `status probe for us-east-2: checking region us-east-2: fetching region status: backend status.internal.example.net returned code 503: connection refused`                      |
| `sa-east-1`    | backend failure | `status probe for sa-east-1: checking region sa-east-1: fetching region status: backend status.internal.example.net returned code 503: connection refused`                      |

Healthy regions (`us-west-1` and anything else not listed above) return
`"operational"` with a nil error.

Constraints:

- Do not change any exported API (`Handler`, `Service`, `FetchStatus`,
  `ErrRegionDown`, `BackendError`), the simulated backend results in
  `store.go`, or which fixture regions fall into which class.
- Each layer must contribute its own prefix to the final message, and the
  reported failure must be the one each layer actually received — the message
  may not be canned or reconstructed at a single layer.
- Edit files in place; stdlib only; `go vet ./...` and `go test ./...` must
  pass with no network access.
