# Testing

## Fast suite

```bash
python -m pytest -q
```

Coverage includes:

- weighted score calculation
- missing/absent/zero semantics
- ranking and ties
- attendance date isolation
- duplicate prevention
- student numbering
- identity matching safety
- AI schema validation
- teacher review/override
- automatic-storage gates
- automatic pass/fail derivation

## Synthetic batch benchmark

```bash
python scripts/benchmark_batch_mock.py
```

The benchmark creates a 120-paper synthetic workload with a mocked AI provider. It measures local submission-processing orchestration only. It intentionally excludes Gemini network/model latency, real handwriting recognition, camera capture time, and provider rate limits.

## Real-school validation before SLA claims

Benchmark using anonymized or consented representative papers across:

- clear printed names
- different handwriting styles
- low light
- perspective distortion
- shadows/glare
- partial crops
- ambiguous names
- duplicate names
- absent names/codes
- multiple answer types
- long/essay answers
- mathematics notation

Track identity precision/recall, question score agreement, teacher override rate, low-confidence routing rate, end-to-end time per paper, and batch error rate.
