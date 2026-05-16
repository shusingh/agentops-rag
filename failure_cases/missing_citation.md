# Missing Citation

## What Went Wrong

The answer uses a retrieved chunk but does not cite it.

## Detection

- The critic reports `missing_citations`.
- Citation precision or recall drops in eval reports.

## Trace Or Log Signal

Compare `retrieval.score_fusion` hit counts with `agent.critic` citation count. A mismatch indicates evidence may have been used without a citation.

## Reproduce Locally

1. Create a draft answer with multiple retrieval hits.
2. Remove one citation from the draft before critique.
3. Run the critic tests or add a focused case in `tests/test_agent_runtime.py`.

## Fix Or Mitigate

- Generate citations directly from retrieval hits.
- Refuse finalization when cited chunk IDs do not cover used evidence.
- Add eval rows requiring multiple expected citation document IDs.
