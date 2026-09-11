# Performance and AI validation benchmark

## Synthetic 120-paper pipeline benchmark

`scripts/benchmark_batch_mock.py` exercises the real batch upload, image validation/preprocessing, database persistence, job tracking, concurrent worker orchestration and result aggregation path for 120 papers while replacing the Gemini call with a deterministic in-process mock.

Run:

```bash
python scripts/benchmark_batch_mock.py
```

The output reports total files, completed/succeeded/failed counts, elapsed time and synthetic papers/second.

### What this benchmark proves

- The application accepts a batch larger than 100 within the configured 150-file request limit.
- Work is processed concurrently using the configured worker pool.
- Each paper has its own persistent submission record.
- Batch progress is persisted and queryable through the scan-job API.
- A failed individual paper does not require the whole batch to be discarded.

### What it does **not** prove

It does not establish Gemini latency, Gemini rate-limit capacity, OCR/handwriting accuracy, identity-match accuracy, or grading correctness. Real deployment validation requires a representative, consented/appropriately governed set of real papers with a teacher-created ground truth and measured false-match/false-grade rates. Gemini API capacity also varies by account tier and model limits, so production concurrency should be tuned from observed metrics rather than a fixed promise.

## Recommended production acceptance gate

Before a school-wide release, evaluate at minimum:

- student identity exact-match, ambiguous-match and wrong-match rates;
- question extraction completeness;
- score agreement against teacher labels by answer type;
- low-confidence routing recall;
- batch failure/retry rate;
- median and p95 processing time;
- API quota/rate-limit behavior;
- duplicate submission prevention;
- audit-log completeness.
