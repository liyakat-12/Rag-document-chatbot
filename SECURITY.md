# DocuMind AI — Security notes

## Threat model (RAG document Q&A)

| Threat | Example | Mitigation |
|--------|---------|------------|
| Prompt injection via uploaded PDFs | “Ignore previous instructions…” | `llm.injection_guard` (default on for LLM providers): untrusted delimiters, system rule never to follow document instructions, delimiter neutralisation, refuse answers that echo the system prompt. Extractive mode only quotes evidence. |
| Citation spoofing | Answer cites a page not in evidence | `citations.validate` (default off until Phase 2 baseline): drop citations that do not map to the evidence set; log with request ID. |
| Path traversal upload | `../../etc/passwd.pdf` | `sanitize_filename` + resolved path must stay under upload dir. |
| Malicious file types | Non-PDF polyglots | Extension allowlist + `%PDF` magic bytes; encrypted PDFs rejected (`/Encrypt`). |
| Oversized uploads | Zip bombs / huge PDFs | `max_upload_size_mb` (default 40). |
| Cache leakage after delete | Stale answer cites deleted doc | Delete removes FAISS vectors, rebuilds BM25, clears semantic cache, unregisters content hash. |
| Duplicate re-index | Same PDF uploaded twice | SHA-256 content hash registry skips re-indexing identical bytes. |
| Secret leakage in errors | Stack traces to clients | Upload/index errors return short safe messages; internals stay in server logs. |

## Limits

- Injection guards reduce risk; they do **not** make LLM mode immune to adaptive attacks.
- Citation validation only checks structural membership in the evidence set — not factual correctness.
- Content-hash dedupe is exact-byte; visually identical re-exports with different bytes still index twice.
- No authentication/authorization layer in this codebase yet (out of scope unless requested).
- Offline extractive mode cannot “obey” injections as instructions; injected text may still appear as quoted evidence.
