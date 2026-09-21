# ADR-0007 — File storage interface with LocalDisk implementation

- **Status:** accepted
- **Context:** Spec mandates a file-storage interface so an S3 backend can be added later.
- **Decision:** `StorageBackend` Protocol with `put`, `head`, `stream`, `delete`, `signed_url` (optional). Default `LocalDiskStorage` writes under `STORAGE_LOCAL_ROOT`. Path layout: `teams/{team_id}/{yyyy}/{mm}/{ulid}_{safe_basename}`. Content-type sniffed from first 4 KB via `python-magic` when available; fallback to signature-based detection. Archives never unpacked.
- **Consequences:**
  - Test backend writes under `tmp_path`, deterministic, fast.
  - S3Storage can be a thin wrapper around `boto3` without touching call sites.
  - Server always computes the destination path; user-provided `filename` is stored separately for display.
- **Alternatives considered:**
  - Direct filesystem everywhere — would couple tests to disk layout and force refactor when adding S3.
