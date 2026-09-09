# workforce_profile

Turns extracted CV or resume text into a typed, editable worker profile. It
uses the text extraction model because the output is structured text. Claims
carry source excerpts, sensitive characteristics are explicitly excluded, and
career preferences are never inferred from work history. The result remains a
draft until the worker confirms it.

## Public surface

`extract_worker_profile(filename: str, text: str) -> ExtractedWorkerProfile`

## Known limitations

The source document establishes claims, not verified truth. Verification and
worker correction happen outside the skill. Scanned-document OCR quality is
inherited from `source_ingestion`.
