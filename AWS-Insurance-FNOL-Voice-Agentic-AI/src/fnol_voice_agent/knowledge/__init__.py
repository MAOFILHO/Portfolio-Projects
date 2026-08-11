"""Knowledge corpus ingestion and retrieval — the CoverageQuestion / RentalTowingEntitlement RAG layer.

Retrieval itself (DynamoDB + in-process brute-force cosine similarity, per ADR-002) is Phase 5 scope. This
package currently holds only the Phase 3 ingestion pipeline (`ingest.py`) — chunking the policy corpus,
embedding it, and loading it into the vector store ADR-002 defines.
"""
