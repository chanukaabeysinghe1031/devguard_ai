# Phase 6A.5 — Query Generation

Version: `hypothesis_query_generator_v1`

`HypothesisSpecificQueryGenerator` builds bounded query families from intents + identifiers.
`RetrievalQuerySanitizer` masks secrets and rejects unsafe text.
`HypothesisQueryDeduplicator` dedupes **within** a hypothesis only.
