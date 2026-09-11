# AI Grading Policy and Architecture

## Goal

Use Gemini as an assessment assistant, not as an invisible autonomous final grader.

## Structured output

The Gemini service requests typed structured output and validates it with Pydantic before persistence.

## Identity pipeline

1. Extract visible name and optional code from the paper.
2. Match against the selected exam class roster.
3. Prefer the normalized student name as the primary identity signal.
4. Treat the sequential class number as corroborating evidence only because roster numbering can change.
5. Require a high identity confidence threshold for automatic score storage.
6. Ambiguous identity remains under teacher control.

## Automatic storage gates

A paper can be automatically committed to the linked assessment only when:

- the student identity is confidently matched;
- every configured exam question is represented exactly once;
- no question is marked for teacher review;
- question confidence meets the configured threshold;
- scores are clamped to the authoritative question maximums;
- a complete exam total can be reconciled;
- no pre-existing final score exists for that student/assessment.

The server then creates or updates the single authoritative `StudentScore` record, marks accepted AI results as accepted, records supported mistakes, and derives pass/fail from the school's configured pass mark.

## Teacher review

Teachers can accept, edit, reject, or recheck AI results. Audit entries preserve meaningful score changes.

## Batch processing

The application supports an application-level queue of up to 150 image files per job, using concurrent processing within a single server process. This improves throughput for a stack of papers, but the local benchmark does not measure external Gemini latency or provider rate limits.

For multi-instance production, move the worker execution to a durable queue/worker system.

## Reliability rules

- Never treat malformed AI JSON as trusted data.
- Never invent unknown question IDs.
- Never silently overwrite an existing final score.
- Never silently resolve ambiguous identity.
- Never report system confidence as a statistical probability guarantee.
- When Gemini is unavailable, preserve the uploaded paper and keep manual grading available.
