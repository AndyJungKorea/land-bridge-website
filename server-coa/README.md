# Land Bridge COA Service

The `/coa` page calls same-origin `/api/coa/lookup?q=...`. Vercel proxies to an
isolated Flask service on the existing VPS. This service does not modify or
depend on the Bioendo catalog, process, database, or Drive gateway.

## Storage and Access

- `COA_DATA/catalog.json` is an immutable, reviewed metadata index, loaded on
  startup. At this volume a database is not required.
- `COA_DATA/private/<sha256>.pdf` contains unchanged manufacturer originals.
- Original PDFs, source ZIPs, metadata indexes, and secrets must not be committed.
- Public exact-match lookup accepts product code, lot, or product code plus lot.
  Case, whitespace and hyphens are normalized; partial queries do not list files.
- Downloads use a 10-minute HMAC link and verify file integrity on every request.
- This is public customer self-service, NOT customer identity authentication.
  Knowledge of a product code permits downloading matching documents.
- No upload/admin endpoint is public. Nginx rate-limits requests.
- Files are hosted privately on the VPS, not Google Drive. Cowork retains the
  original ZIP and verification artifacts as a separate recovery source.

## Operations

Service: `landbridge-coa`, loopback port `5196`, user `landbridgecoa`.
Environment: `/etc/landbridge-coa.env` (root-only; never copy to reports).
Release path: `/opt/landbridge-coa/releases/20260929-v1`.
Active symlink: `/opt/landbridge-coa/current`.

For a new batch, preserve the source, separate MSDS, deduplicate by SHA-256,
compare Cat. No. and Batch No. with PDF contents, and quarantine ambiguity.
Build a NEW complete release directory with the reviewed catalog and originals.
Verify all hashes and lookup tests before switching the `current` symlink and
restarting ONLY `landbridge-coa`. The original installation script is not an
update script; do not rerun it over an existing release.

For rollback, switch `current` to the previous verified release and restart this
service only. Do not restore an old shared nginx config over other teams' changes.
If routing removal is needed, remove only the Landbridge include after a fresh
read, run `nginx -t`, then reload nginx.

The source catalog may include historical/expired product batches. A COA lookup
is an archive retrieval and does not certify present inventory or shelf life.

## Tests

`python -m unittest discover -s server-coa -v`

Local verification must cover exact/normalized identifiers, empty/missing/error
states, original file hashes, invalid/expired signatures, private route denial,
and desktop/mobile search and download. Repeat on the production domain.
