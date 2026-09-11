import pytest
from app.schemas import AIGradingOutput


def valid():
    return {
        'identity': {
            'name_found': True,
            'detected_name': 'Abdi Bekele',
            'detected_code': 'ST001',
            'confidence': 0.96,
            'evidence': 'Student name is visible in the header.'
        },
        'questions': [{
            'question_id': 1, 'student_answer': 'x=5', 'expected_answer': 'x=5',
            'score': 3, 'maximum_score': 3, 'confidence': 0.98,
            'reason': 'Exact match', 'mistake_type': 'None', 'topic': 'Algebra',
            'subtopic': 'Linear equations', 'feedback': 'Correct.', 'needs_teacher_review': False
        }],
        'overall_feedback': 'Strong'
    }


def test_ai_schema_accepts_identity_and_results():
    obj = AIGradingOutput.model_validate(valid())
    assert obj.identity.detected_name == 'Abdi Bekele'
    assert obj.questions[0].confidence == 0.98


def test_ai_schema_rejects_bad_confidence():
    value = valid(); value['identity']['confidence'] = 1.7
    with pytest.raises(Exception): AIGradingOutput.model_validate(value)
