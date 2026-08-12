"""Knowledge corpus ingestion and retrieval — the CoverageQuestion / RentalTowingEntitlement RAG layer.

`ingest.py` (Phase 3): chunks the policy corpus, embeds it, loads it into the DynamoDB vector store ADR-002
defines. `retrieve.py` (Phase 5, Stage 3): the read half — brute-force cosine similarity search over those
same chunks, in-process, per ADR-002.
"""
