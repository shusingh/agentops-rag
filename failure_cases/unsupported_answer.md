# Unsupported Answer

## What Went Wrong

The final answer contains claims that are not present in retrieved evidence.

## Detection

- The critic sets `supported=false`.
- `unsupported_claims` is non-empty.
- Eval unsupported claim rate increases.

## Trace Or Log Signal

Inspect `agent.model_call`, `agent.critic`, and `agent.finalizer`. A refused finalizer response after a non-empty draft indicates the critic blocked unsupported output.

## Reproduce Locally

1. Modify a test draft to include facts absent from the retrieved chunk.
2. Run `python -m pytest tests/test_agent_runtime.py`.

## Fix Or Mitigate

- Keep final answers extractive until the critic is stronger.
- Require citations for every evidence-backed sentence.
- Add a stricter claim decomposition step before finalization.
