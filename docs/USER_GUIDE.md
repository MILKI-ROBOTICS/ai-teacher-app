# User Guide

## First launch

The academic workspace is intentionally empty. Sign in with the bootstrap teacher account configured in `.env`, then create your school settings, classes, students, subjects and assessment types.

## Students

Open **Students** → **+ Add student**. Enter the teacher's real student name and code. Edit or archive a profile when needed. No sample students are inserted automatically.

## Assessments and scores

Open **Setup & Settings** to create assessment types with maximum score and weight. Create an assessment from **Scores** and attach it to a class/subject when appropriate. In the score grid, enter a score and press Enter; the value is saved and focus moves to the next student. Empty, zero, absent, excused and not-applicable remain distinct.

## Attendance

Open **Attendance**, choose the class and date. Every student has two circular controls:

- **P** = Present
- **A** = Absent

One tap saves immediately. Selecting a different date loads that date's stored record; previous days are not overwritten. `P` and `A` keyboard shortcuts can be used at the desk, and the browser stores failed attendance writes in IndexedDB for retry when connectivity returns.

## AI Checker

1. Select the exam.
2. Choose **Open camera** and capture the paper inside the app, or use **Upload photo**.
3. Do **not** select a student first.
4. Gemini reads a visible student name/code and the answers.
5. The server matches that identity against the students in the exam's class.
6. If the match is confident, the paper is linked automatically.
7. If it is ambiguous, candidate student profiles are shown for one-time teacher assignment.
8. Question-level AI suggestions show score, confidence, reason and feedback.
9. The teacher accepts/edits/rejects results. The authoritative assessment score is stored only after reviewed results are resolved.

For a large pile of papers, the teacher can keep the camera workflow going in any order. Desktop also supports selecting multiple image files for sequential processing.

## Exam setup

Use the **Exam setup** panel in AI Checker to create an exam and add questions. Add answer-key/rubric guidance so the model has explicit marking evidence.

## Analytics

Analytics is evidence-driven: class average, pass rate, attendance, support count, ranking and most common stored mistake. The system does not claim a causal explanation for changes in performance.
