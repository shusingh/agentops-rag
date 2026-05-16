# Bad Retrieval

## What Went Wrong

The retriever returns chunks that are lexically or semantically close to the question but do not actually answer it. This can happen when multiple policies share vocabulary such as "review", "retention", or "logging".

## Detection

- Eval citation recall drops.
- The critic refuses because retrieved evidence does not support the drafted answer.
- `retrieval.bm25_hits` and `retrieval.vector_hits` are nonzero, but answer quality is poor.

## Trace Or Log Signal

Look for `retrieval.bm25_search`, `retrieval.vector_search`, and `retrieval.score_fusion` spans with the tenant ID and top-k. Compare the top chunks against the critic span rationale.

## Reproduce Locally

1. Add two demo chunks with overlapping terms.
2. Ask a question where only one chunk contains the required answer.
3. Run `python -m pytest tests/test_hybrid_retrieval.py`.

## Fix Or Mitigate

- Tune fusion weights.
- Add reranking.
- Add metadata filters.
- Expand eval cases for ambiguous terminology.
