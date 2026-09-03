Ops report on `worker.py`: under 40 concurrent logins the endpoint takes ~5
seconds, and while those logins run, unrelated requests on the same event loop
stall badly. Make 40 concurrent `authenticate()` calls complete in under 3
seconds total and keep the event loop responsive the whole time.

Constraints:
- Token values must remain byte-identical — do not change `_derive_token`, its
  iteration count, or the token format.
- The session-store round trip must still happen for every login.
- Keep `authenticate` as an async function with the same signature.
- Edit only `worker.py`; stdlib only.
