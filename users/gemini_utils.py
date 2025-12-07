import google.generativeai as genai
from django.conf import settings
import json
import time
import base64

def initialize_gemini():
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
        response = model.generate_content('Test')
        return model
    except Exception as e:
        print(f'Failed to initialize gemini-2.0-flash-exp: {str(e)}')
        try:
            model = genai.GenerativeModel('models/gemini-2.0-flash-thinking-exp')
            response = model.generate_content('Test')
            return model
        except Exception as e:
            print(f'Failed to initialize gemini-2.0-flash-thinking-exp: {str(e)}')
            raise Exception('Failed to initialize any Gemini model')

try:
    model = initialize_gemini()
except Exception as e:
    print(f'Warning: Failed to initialize Gemini model: {str(e)}')
    model = None

# Use flash model for faster question generation
try:
    fast_model = genai.GenerativeModel('models/gemini-2.5-flash')
except:
    fast_model = model

def generate_interview_questions(role, experience, interview_type, random_seed=None):
    # Try API first, but fall back to pre-generated questions immediately if quota exceeded
    if not fast_model and not model:
        print('Gemini model not initialized, using pre-generated questions')
        return generate_fallback_questions(role, experience, interview_type)

    type_mapping = {
        'technical': 'technical skills like coding, system design, algorithms',
        'behavioral': 'soft skills like teamwork, leadership, communication',
        'mixed': 'both technical and behavioral aspects'
    }

    focus = type_mapping.get(interview_type, type_mapping['mixed'])

    # Use a simpler prompt to avoid quota issues
    prompt = f"""Generate 10 {interview_type} interview questions for a {role} with {experience} years experience.

Format: Numbered list only."""

    try:
        # Use fast_model for quicker generation
        model_to_use = fast_model if fast_model else model
        response = model_to_use.generate_content(
            prompt,
            generation_config={'temperature': 0.7, 'max_output_tokens': 512}
        )

        # Handle cases where response might be blocked
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            # Check if response was actually generated
            if not candidate.content.parts:
                print(f'Warning: Empty response from API, using pre-generated questions')
                return generate_fallback_questions(role, experience, interview_type)

        text = response.text.strip()
        questions = []
        for line in text.split('\n'):
            line = line.strip()
            if line and line[0].isdigit():
                q = line.split('.', 1)[-1].strip()
                if q and len(q) > 10:
                    questions.append(q)

        if len(questions) >= 5:
            return questions[:10]
        else:
            print(f'Only {len(questions)} valid questions extracted, using pre-generated questions')
            return generate_fallback_questions(role, experience, interview_type)

    except Exception as e:
        print(f'API error: {str(e)}, using pre-generated questions')
        # Return fallback questions if API fails
        return generate_fallback_questions(role, experience, interview_type)

def generate_fallback_questions(role, experience, interview_type):
    """Generate fallback questions when API is unavailable or blocked"""
    
    technical_questions = [
        'Describe your experience with system design and how you approach building scalable applications.',
        'Walk me through a challenging technical problem you solved. How did you approach it?',
        'Explain the key concepts you use for database optimization in your projects.',
        'What design patterns do you use most frequently and why?',
        'Describe your experience with code review and how you provide constructive feedback.',
        'How do you handle debugging complex issues in production environments?',
        'What tools and practices do you use for version control and collaboration?',
        'Explain a time when you had to refactor legacy code. What was your approach?',
        'How do you ensure code quality and maintainability in your projects?',
        'Describe your experience with testing strategies and automation.'
    ]
    
    behavioral_questions = [
        'Tell me about a time you worked in a team and how you contributed to the project.',
        'Describe a conflict with a colleague and how you resolved it.',
        'Tell me about your greatest professional achievement.',
        'How do you handle working under pressure and tight deadlines?',
        'Describe a time you had to learn something new quickly.',
        'Tell me about a failure and what you learned from it.',
        'How do you approach mentoring or helping junior team members?',
        'Describe your communication style and how you handle disagreements.',
        'Tell me about a time you took initiative on a project.',
        'How do you stay motivated and engaged in your work?'
    ]
    
    mixed_questions = technical_questions[:5] + behavioral_questions[:5]
    
    if interview_type == 'technical':
        return technical_questions
    elif interview_type == 'behavioral':
        return behavioral_questions
    else:
        return mixed_questions

def analyze_response(question, answer, role, experience_level):
    # Try API first, but fall back to pre-generated feedback immediately if quota exceeded
    if not model:
        print('Gemini model not initialized, using pre-generated feedback')
        return generate_fallback_feedback(question, answer, role, experience_level)

    try:
        prompt = f'Analyze this {role} interview response ({experience_level} years exp). Q: {question} A: {answer}. Return JSON with: score (1-10), strengths (2-3 items), improvements (2-3 items).'
        response = model.generate_content(prompt, generation_config={'max_output_tokens': 256})
        response_text = response.text.strip()

        try:
            feedback = json.loads(response_text)
            # Validate required fields
            if all(k in feedback for k in ['score', 'strengths', 'improvements']):
                # Ensure types are correct
                feedback['score'] = int(feedback['score']) if isinstance(feedback['score'], (int, float)) else 5
                feedback['strengths'] = feedback['strengths'] if isinstance(feedback['strengths'], list) else ['Good response']
                feedback['improvements'] = feedback['improvements'] if isinstance(feedback['improvements'], list) else ['Could be more detailed']
                return feedback
        except (json.JSONDecodeError, ValueError):
            # If not valid JSON, create structured response
            pass

    except Exception as e:
        print(f'API error generating feedback: {str(e)}, using pre-generated feedback')

    # Return fallback feedback if API fails
    return generate_fallback_feedback(question, answer, role, experience_level)

def generate_fallback_feedback(question, answer, role, experience_level):
    """Generate pre-defined feedback based on answer characteristics"""
    answer_length = len(answer.strip())
    has_keywords = any(word in answer.lower() for word in ['experience', 'worked', 'developed', 'learned', 'team', 'project'])

    # Base score based on answer quality
    base_score = 5
    if answer_length > 100:
        base_score += 2
    if has_keywords:
        base_score += 1
    if answer_length > 200:
        base_score += 1

    base_score = min(base_score, 10)

    # Pre-defined feedback templates
    strengths = ['Clear and direct response', 'Addresses the question appropriately']
    improvements = ['Consider adding specific examples', 'Could elaborate on key points']

    if answer_length < 50:
        improvements.append('Response could be more detailed')
        base_score = max(base_score - 1, 3)
    elif answer_length > 300:
        strengths.append('Comprehensive answer provided')

    if has_keywords:
        strengths.append('Includes relevant experience details')

    return {
        'score': base_score,
        'strengths': strengths[:3],  # Limit to 3 items
        'improvements': improvements[:3],  # Limit to 3 items
        'technical_accuracy': base_score,
        'communication_clarity': base_score
    }

def analyze_voice_data(audio_text):
    if not model or not audio_text:
        return None

    try:
        prompt = f'Analyze this interview voice response: {audio_text}'
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {
            'clarity': 5,
            'pace': 'Analysis unavailable',
            'tone': 'Analysis unavailable',
            'improvements': [f'Error: {str(e)}']
        }

def analyze_video_interaction(video_base64):
    """Analyze video interaction using Gemini Vision API"""
    if not model or not video_base64:
        return None

    try:
        image_parts = [
            {
                'mime_type': 'image/jpeg',
                'data': base64.b64decode(video_base64)
            }
        ]

        prompt = """Analyze this interview video frame for:
        1. Body language
        2. Eye contact
        3. Professional appearance
        4. Overall presence

        Provide feedback in JSON format with those categories."""

        response = model.generate_content([prompt, image_parts[0]])
        return json.loads(response.text)
    except Exception as e:
        return {
            'error': str(e),
            'body_language': 'Unable to analyze',
            'eye_contact': 'Unable to analyze',
            'professional_appearance': 'Unable to analyze',
            'overall_presence': 'Unable to analyze'
        }
