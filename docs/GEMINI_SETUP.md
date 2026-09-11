# Gemini Setup

The application uses Google's `google-genai` Python SDK and keeps Gemini behind `GeminiService`.

1. Create a Gemini API key using Google's current Gemini API process.
2. Copy `.env.example` to `.env`.
3. Set:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

4. Restart the server.
5. Open AI Checker.
6. Select an exam with questions and answer-key/rubric guidance.
7. Open the camera and capture an answer sheet.

The server sends the photographed sheet plus exam context to Gemini. The model is instructed to extract a visible student identity and return structured question-level grading data. The response is validated with Pydantic before any AI result is stored.

Never place `GEMINI_API_KEY` in browser JavaScript, HTML, source control, or a client-side environment variable.
