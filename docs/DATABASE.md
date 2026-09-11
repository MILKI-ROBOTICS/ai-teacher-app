# Database

The normalized schema stores users, schools, classes, students, subjects, assessment types, assessments, student scores, date-specific attendance, exams, questions, submissions, AI results, mistakes, teacher comments and audit logs.

Important uniqueness rules:

- `(student_id, assessment_id)` on `student_scores`.
- `(student_id, date)` on `attendance`.
- `(exam_id, question_no)` on `questions`.

A submission's `student_id` is nullable until AI identity matching or teacher assignment resolves the paper. The submission also stores the detected name/code, identity confidence and identity status.

Run:

```bash
alembic upgrade head
```

The application also creates tables on startup for simple local use. It creates only the bootstrap teacher and workspace; it does not seed students, scores, classes, subjects, assessment types or exam papers.
