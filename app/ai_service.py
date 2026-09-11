from pathlib import Path
import json

from pydantic import ValidationError
from .config import settings
from .schemas import AIGradingOutput

SYSTEM_PROMPT = """
You are the AI assessment assistant inside a teacher-controlled grading system.
Read the submitted answer-sheet image carefully.
1) Identify the student's name and/or student code if visible on the paper. Never invent identity.
2) Grade only from the supplied exam questions and answer key/rubric information. If an answer key is missing, do not invent an expected answer; use null and explain the limitation.
3) Return at most one result for each known question ID. Never invent question IDs.
4) Give a conservative score, confidence (0..1 as a reliability signal, not a probability guarantee), reason, mistake type, topic, subtopic, and feedback.
5) If handwriting is unreadable, the answer is ambiguous, the question is not visible, or identity is uncertain, set needs_teacher_review=true.
6) Treat a blank answer as blank only when the page visibly shows no answer. Do not infer missing content.
7) Never claim certainty when evidence is weak.
8) Preserve the teacher's final authority.
""".strip()


class GeminiUnavailable(RuntimeError):
    pass


class GeminiService:
    def __init__(self):
        self.enabled = False
        self.client = None
        self.import_error = None
        if not settings.gemini_api_key:
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=settings.gemini_api_key)
            self.enabled = True
        except Exception as exc:
            self.import_error = str(exc)

    def analyze_answer_sheet(self, image_path: str, mime_type: str, questions: list[dict], answer_key: str | None) -> AIGradingOutput:
        if not self.enabled or self.client is None:
            raise GeminiUnavailable("Gemini is not configured. Add GEMINI_API_KEY to .env")
        try:
            import base64
            encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            prompt = (
                f"{SYSTEM_PROMPT}\n\nExam questions:\n{json.dumps(questions, ensure_ascii=False, indent=2)}\n\n"
                f"Answer key / rubric:\n{answer_key or 'No answer key supplied. Do not invent an expected answer; use only clearly supported facts.'}\n\n"
                "Return JSON matching the supplied schema."
            )
            interaction = self.client.interactions.create(
                model=settings.gemini_model,
                input=[
                    {"type": "image", "data": encoded, "mime_type": mime_type},
                    {"type": "text", "text": prompt},
                ],
                system_instruction=SYSTEM_PROMPT,
                generation_config={"thinking_level": "low"},
                response_format={"type": "text", "mime_type": "application/json", "schema": AIGradingOutput.model_json_schema()},
                store=False,
            )
            return AIGradingOutput.model_validate_json(interaction.output_text)
        except (ValidationError, ValueError, TypeError) as exc:
            raise GeminiUnavailable(f"Gemini returned invalid structured output: {exc}") from exc
        except Exception as exc:
            raise GeminiUnavailable(f"Gemini request failed: {exc}") from exc
