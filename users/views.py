from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, FileResponse, JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Profile
from .serializers_clean import (
    InterviewStartSerializer,
    InterviewStartResponseSerializer,
    InterviewFeedbackSerializer,
    InterviewFeedbackResponseSerializer
)
from .services.mistral_service import get_mistral_service
import json
import base64

def home(request):
    context = {}
    if request.user.is_authenticated:
        context['authenticated'] = True
    from .models import Testimonial
    context['testimonials'] = Testimonial.objects.all()
    return render(request, 'index.html', context)

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
    return render(request, 'login.html')

def signup_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        years = request.POST.get('years')

        if User.objects.filter(username=email).exists():
            # If account exists, attempt to authenticate using provided password
            user = authenticate(request, username=email, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Account exists but password is incorrect.')
        else:
            try:
                user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
                # ensure profile exists (use get_or_create to be resilient)
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.full_name = name
                profile.role = role or ''
                try:
                    profile.years_experience = int(years) if years else None
                except ValueError:
                    profile.years_experience = None
                profile.save()
                messages.success(request, 'Account created and logged in.')
                auth_login(request, user)
                return redirect('dashboard')
            except Exception as e:
                # surface the error to the user and log (simple)
                messages.error(request, f'Could not create account: {e}')
    return render(request, 'signup.html')

def logout_view(request):
    auth_logout(request)
    return redirect('home')

@login_required
def dashboard(request):
    # Pass profile safely to the template so signup details can be displayed
    profile = getattr(request.user, 'profile', None)
    from feedback.models import InterviewResult
    recent_interviews = InterviewResult.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'dashboard.html', {'user': request.user, 'profile': profile, 'recent_activity': recent_interviews})

def faq(request):
    return render(request, 'faq.html')

def testimonial(request):
    return render(request, 'testimonial.html')

@login_required
def profile_view(request):
    """Show the logged-in user's profile details."""
    profile = getattr(request.user, 'profile', None)
    return render(request, 'profile.html', {'profile': profile, 'user': request.user})

@login_required
def profile_edit(request):
    """Edit the logged-in user's profile (full name, role, years_experience)."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        role = request.POST.get('role', '').strip()
        years = request.POST.get('years', '').strip()

        profile.full_name = full_name
        profile.role = role
        try:
            profile.years_experience = int(years) if years != '' else None
        except ValueError:
            messages.error(request, 'Years of experience must be a number.')
            return render(request, 'profile_edit.html', {'profile': profile})

        profile.save()
        # Sync first_name for small display convenience
        if full_name:
            request.user.first_name = full_name.split(' ', 1)[0]
            request.user.save()

        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    return render(request, 'profile_edit.html', {'profile': profile})

@login_required
def mock_interview_view(request):
    # Map experience levels to numeric values
    experience_mapping = {
        "Fresher": 0,
        "Junior": 1,
        "Mid": 3,
        "Senior": 5
    }

    if request.method == 'POST':
        name = request.POST.get('name')
        role = request.POST.get('role')
        experience = request.POST.get('experience')
        interview_type = request.POST.get('interview_type')
        mode = request.POST.get('mode')
        webcam_enabled = (mode == 'voice')

        if not all([name, role, experience, interview_type, mode]):
            messages.error(request, 'All fields are required.')
            return redirect('dashboard')

        # Convert experience to numeric value
        experience_numeric = experience_mapping.get(experience, None)
        if experience_numeric is None:
            messages.error(request, 'Invalid experience level provided.')
            return redirect('dashboard')

        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.full_name = name
            profile.role = role
            profile.years_experience = experience_numeric
            profile.save()

        try:
            print(f"Generating static questions for {role} position, {experience} years, type: {interview_type}")
            questions = generate_fallback_questions(role, experience_numeric, interview_type)

            if not questions or len(questions) < 5:
                messages.error(request, 'Failed to generate enough interview questions. Please try again.')
                return redirect('dashboard')

            print(f"Successfully generated {len(questions)} questions")
            messages.success(request, 'Interview questions generated successfully!')

        except Exception as e:
            error_msg = str(e)
            print(f"Error generating questions: {error_msg}")
            messages.error(request, 'An error occurred while generating questions. Please try again.')
            return redirect('dashboard')

        request.session['interview_questions'] = questions
        request.session['current_question_idx'] = 0
        request.session['interview_answers'] = []
        request.session['voice_transcripts'] = []
        request.session['interaction_feedbacks'] = []
        request.session['interview_data'] = {
            'name': name,
            'role': role,
            'experience': experience,
            'interview_type': interview_type,
            'mode': mode,
            'webcam_enabled': webcam_enabled,
            'pure_voice': mode == 'voice'
        }
        return redirect('interview_run')

    return redirect('dashboard')

@login_required
def interview_run_view(request):
    from feedback.models import InterviewResult

    questions = request.session.get('interview_questions', [])
    idx = request.session.get('current_question_idx', 0)
    answers = request.session.get('interview_answers', [])
    interview_data = request.session.get('interview_data', {})
    mode = interview_data.get('mode', 'text')
    webcam_enabled = interview_data.get('webcam_enabled', False)
    question_audios = request.session.get('question_audios', {})

    # Map experience levels to numeric values
    experience_mapping = {
        "Junior": 1,
        "Mid": 3,
        "Senior": 5
    }

    # Check if interview data exists
    if not interview_data or not questions:
        messages.error(request, 'No active interview. Please start a new interview.')
        return redirect('dashboard')

    if request.method == 'POST':
        result_id = request.POST.get('result_id', '')
        audio_blob = request.POST.get('audio_blob', '')
        uploaded_files = request.FILES if hasattr(request, 'FILES') else {}
        uploaded_main_audio = uploaded_files.get('audio_file') if uploaded_files else None
        webcam_frames = request.POST.get('webcam_frames', '[]')
        answer = request.POST.get('answer', '')
        voice_transcripts = request.session.get('voice_transcripts', [])
        interaction_feedbacks = request.session.get('interaction_feedbacks', [])

        # Convert experience to numeric value
        experience_str = interview_data.get('experience', '0')
        experience = experience_mapping.get(experience_str, 0)

        # Capture per-question audio
        if audio_blob and idx < len(questions):
            question_audios[str(idx)] = audio_blob
            request.session['question_audios'] = question_audios

        # Transcribe audio if provided
        transcript = ""
        if audio_blob or uploaded_main_audio:
            try:
                if uploaded_main_audio:
                    audio_bytes = uploaded_main_audio.read()
                else:
                    audio_bytes = base64.b64decode(audio_blob.split(',')[1])

                # Try Whisper first
                try:
                    import whisper
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tf:
                        tf.write(audio_bytes)
                        temp_name = tf.name
                    try:
                        model = whisper.load_model('base')
                        wres = model.transcribe(temp_name)
                        transcript = (wres.get('text') or '').strip()
                    finally:
                        try:
                            os.remove(temp_name)
                        except OSError:
                            pass
                except Exception as e:
                    print(f"Whisper transcription failed: {e}")
                    transcript = "[Audio transcription failed]"

            except Exception as e:
                print(f"Audio transcription error: {e}")
                transcript = "[Audio transcription failed]"

        # Store the transcript and answer
        if idx < len(questions):
            voice_transcripts.append(transcript)
            answers.append(answer)
            request.session['voice_transcripts'] = voice_transcripts
            request.session['interview_answers'] = answers

        # Check if this is the final submission
        if result_id == 'final_submit' or idx + 1 >= len(questions):
            # Generate AI feedback
            questions_answers = []
            for i, q in enumerate(questions):
                ans = answers[i] if i < len(answers) else ""
                trans = voice_transcripts[i] if i < len(voice_transcripts) else ""
                final_answer = trans if trans and trans != "[Audio transcription failed]" else ans
                questions_answers.append({
                    'question': q,
                    'answer': final_answer
                })

            try:
                # Use static feedback instead of AI generation
                feedback_data = {
                    "overall_score": 75,
                    "grade_label": "B",
                    "summary": "Interview completed successfully. You demonstrated good communication skills and provided thoughtful responses.",
                    "strengths": ["Clear communication", "Relevant examples provided", "Good problem-solving approach"],
                    "weaknesses": ["Could elaborate more on technical details", "Some responses could be more concise"],
                    "suggestions": ["Practice explaining technical concepts in simpler terms", "Focus on quantifying achievements"],
                    "questions": questions_answers
                }
                ai_feedback_json = json.dumps(feedback_data)
            except Exception as e:
                print(f"Error generating feedback: {e}")
                feedback_data = {
                    "overall_score": 70,
                    "grade_label": "C",
                    "summary": "Feedback generation encountered an error. Please review your responses manually.",
                    "strengths": ["Completed the interview"],
                    "weaknesses": ["Technical issues during feedback generation"],
                    "suggestions": ["Retry the interview if possible"],
                    "questions": []
                }
                ai_feedback_json = json.dumps(feedback_data)

            # Save InterviewResult
            result = InterviewResult.objects.create(
                user=request.user,
                name=interview_data.get('name', ''),
                role=interview_data.get('role', ''),
                experience=experience,
                interview_type=interview_data.get('interview_type', 'mixed'),
                mode=mode,
                webcam_enabled=webcam_enabled,
                questions=questions,
                answers=answers,
                voice_transcripts=voice_transcripts,
                ai_feedback=ai_feedback_json,
                overall_score=feedback_data.get('overall_score'),
                grade_label=feedback_data.get('grade_label')
            )

            # Clear session data
            keys_to_clear = [
                'interview_questions', 'current_question_idx', 'interview_answers',
                'voice_transcripts', 'interaction_feedbacks', 'interview_data',
                'question_audios', 'question_transcripts', 'question_audio_clips'
            ]
            for key in keys_to_clear:
                request.session.pop(key, None)

            messages.success(request, 'Interview completed! View your feedback below.')
            return redirect('result_detail', pk=result.pk)

        # Move to the next question
        request.session['current_question_idx'] = idx + 1
        return redirect('interview_run')

    return render(request, 'interview_run.html', {
        'questions': questions,
        'question': questions[idx] if idx < len(questions) else None,
        'answers': answers,
        'mode': mode,
        'webcam_enabled': webcam_enabled,
        'total': len(questions),
        'current_idx': idx,
        'interview_data': interview_data
    })

@login_required
def results_view(request):
    from feedback.models import InterviewResult
    results = InterviewResult.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'results.html', {'results': results})

@login_required
def result_detail_view(request, pk):
    """Show detailed feedback for a single InterviewResult."""
    from feedback.models import InterviewResult
    import json

    try:
        result = InterviewResult.objects.get(pk=pk, user=request.user)
    except InterviewResult.DoesNotExist:
        if request.user.is_staff:
            result = get_object_or_404(InterviewResult, pk=pk)
        else:
            messages.error(request, 'Requested feedback not found.')
            return redirect('results')

    # Parse AI feedback JSON
    feedback = None
    if result.ai_feedback:
        try:
            feedback = json.loads(result.ai_feedback)
        except json.JSONDecodeError:
            feedback = {'error': 'Failed to parse feedback data'}

    context = {
        'result': result,
        'feedback': feedback,
    }
    return render(request, 'result_detail.html', context)

@login_required
def upload_question_clip(request):
    """Accept per-question audio clip."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        question_idx = int(request.POST.get('question_idx', -1))
        audio_file = request.FILES.get('audio_file')

        if not audio_file or question_idx < 0:
            return JsonResponse({'error': 'Missing audio_file or question_idx'}, status=400)

        # Read audio bytes
        audio_bytes = audio_file.read()

        # Store clip in session
        if 'question_audio_clips' not in request.session:
            request.session['question_audio_clips'] = {}

        request.session['question_audio_clips'][str(question_idx)] = {
            'filename': audio_file.name,
            'content_type': audio_file.content_type
        }

        # Attempt transcription
        transcript = "Audio received"
        try:
            import whisper
            import tempfile, os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tf:
                tf.write(audio_bytes)
                temp_name = tf.name

            try:
                model = whisper.load_model('base')
                result_whisper = model.transcribe(temp_name, language='en')
                transcript = (result_whisper.get('text') or '').strip()
            finally:
                try:
                    os.unlink(temp_name)
                except:
                    pass
        except Exception as e:
            print(f"Whisper transcription failed: {e}")
            transcript = "Audio received but transcription failed."

        # Store transcription in session
        if 'question_transcripts' not in request.session:
            request.session['question_transcripts'] = {}
        request.session['question_transcripts'][str(question_idx)] = transcript
        request.session.modified = True

        return JsonResponse({
            'success': True,
            'question_idx': question_idx,
            'transcript': transcript
        })

    except Exception as e:
        print(f"upload_question_clip error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def download_interview_media(request, pk, kind):
    """Protected media download."""
    from feedback.models import InterviewResult
    result = get_object_or_404(InterviewResult, pk=pk)
    if not request.user.is_staff:
        raise Http404()

    if kind == 'audio' and result.audio_file:
        return FileResponse(result.audio_file.open('rb'), as_attachment=True, filename=result.audio_file.name.split('/')[-1])
    if kind == 'frames' and result.video_frames_zip:
        return FileResponse(result.video_frames_zip.open('rb'), as_attachment=True, filename=result.video_frames_zip.name.split('/')[-1])
    raise Http404()

def stats_view(request):
    from feedback.models import InterviewResult
    total_users = User.objects.count()
    total_interviews = InterviewResult.objects.count()
    total_feedbacks = InterviewResult.objects.exclude(ai_feedback='').count()
    return JsonResponse({
        'total_users': total_users,
        'total_interviews': total_interviews,
        'total_feedbacks': total_feedbacks
    })

def feature_mock_interviews(request):
    return render(request, 'feature_mock_interviews.html')

def feature_feedback(request):
    return render(request, 'feature_feedback.html')

def feature_tips(request):
    return render(request, 'feature_tips.html')

def start_interview(request):
    if request.method == 'POST':
        role = request.POST.get('role')
        experience_level = request.POST.get('experience_level')
        number_of_questions = int(request.POST.get('number_of_questions', 5))

        try:
            questions = generate_fallback_questions(role, experience_level, 'mixed')  # Use static questions
            request.session['interview_questions'] = questions
            request.session['current_question_idx'] = 0

            return render(request, 'interview_run.html', {
                'question': questions[0] if questions else "No questions generated.",
                'total': len(questions),
                'current_idx': 0,
                'webcam_enabled': False
            })
        except Exception as e:
            print(f"Error during question generation: {e}")
            return render(request, 'interview_run.html', {
                'question': "An error occurred while generating questions. Please try again later.",
                'total': 0,
                'current_idx': 0,
                'webcam_enabled': False
            })

    return render(request, 'interview_run.html')

def complete_interview(request):
    if request.method == 'POST':
        return render(request, 'feedback.html')

def generate_feedback_view(request):
    if request.method == 'POST':
        role = request.POST.get('role')
        questions = request.POST.getlist('questions')
        candidate_answers = request.POST.getlist('candidate_answers')

        feedback = generate_feedback(role, questions, candidate_answers)
        return JsonResponse({"feedback": feedback})

    return JsonResponse({"error": "Invalid request method."}, status=400)


def generate_interview_questions(role, experience, interview_type):
    """Generate interview questions using Mistral AI with fallback."""
    try:
        mistral_service = get_mistral_service()
        questions = mistral_service.generate_questions(role, experience, interview_type)
        if questions and len(questions) >= 5:
            return questions
        else:
            return generate_fallback_questions(role, experience, interview_type)
    except Exception as e:
        print(f"Error generating questions: {e}")
        return generate_fallback_questions(role, experience, interview_type)


def generate_fallback_questions(role, experience, interview_type):
    """Generate fallback questions based on role, experience, and type."""
    
    # Fresher/Junior level questions
    fresher_technical = [
        f"Can you explain the basic concepts of {role} that you've learned?",
        "What programming languages are you familiar with and why?",
        "Can you walk us through a simple project you've built?",
        "How do you approach learning new technologies?",
        "What are the fundamentals you consider important in this field?"
    ]
    
    fresher_behavioral = [
        "Tell us about yourself and your background.",
        "What motivated you to pursue a career in {role}?",
        "Describe a time when you learned something new quickly.",
        "How do you handle feedback or criticism?",
        "Why are you interested in this position?"
    ]
    
    fresher_mixed = [
        f"Can you tell us about your interest in becoming a {role}?",
        "What are the key skills you've developed so far?",
        "Describe a project or assignment you worked on in college/learning.",
        "How do you approach problem-solving?",
        "Where do you see yourself in your career in the next 2-3 years?"
    ]
    
    # Mid-level questions
    mid_technical = [
        f"Can you explain your experience with {role}-related technologies?",
        "Describe a challenging technical problem you've solved.",
        "How do you stay updated with the latest developments in your field?",
        "What tools and frameworks are you proficient in for this role?",
        "How would you approach debugging a complex issue?"
    ]
    
    mid_behavioral = [
        "Tell me about a time you worked in a team to achieve a goal.",
        "Describe a situation where you had to learn something new quickly.",
        "How do you handle constructive criticism?",
        "Give an example of how you've handled a difficult stakeholder.",
        "What motivates you in your work?"
    ]
    
    mid_mixed = [
        f"What are your key strengths as a {role}?",
        "Describe your experience level and how it aligns with this role.",
        "How do you approach complex problem-solving in your work?",
        "Tell me about a significant project you're proud of and why.",
        "How do you balance technical depth with broader business understanding?"
    ]
    
    # Senior-level questions
    senior_technical = [
        f"How have you architected solutions as a {role}?",
        "Describe your approach to designing scalable systems.",
        "How do you mentor junior developers in technical skills?",
        "What's your philosophy on code quality and technical debt?",
        "How do you stay ahead of industry trends and emerging technologies?"
    ]
    
    senior_behavioral = [
        "Tell me about your leadership experience and approach.",
        "Describe a situation where you drove significant change.",
        "How do you balance technical and people management?",
        "Give an example of how you've influenced organization-wide decisions.",
        "What's your approach to building and maintaining high-performing teams?"
    ]
    
    senior_mixed = [
        f"How have you grown as a {role} over your career?",
        "Describe your approach to strategic technical decisions.",
        "How do you contribute to company vision and strategy?",
        "Tell me about your most significant impact on a project.",
        "Where do you want to take your career in the next 5 years?"
    ]
    
    # Determine experience level
    if experience <= 1:
        if interview_type == 'technical':
            questions = fresher_technical
        elif interview_type == 'behavioral':
            questions = fresher_behavioral
        else:  # mixed
            questions = fresher_mixed
    elif experience <= 3:
        if interview_type == 'technical':
            questions = mid_technical
        elif interview_type == 'behavioral':
            questions = mid_behavioral
        else:  # mixed
            questions = mid_mixed
    else:  # Senior (experience > 3)
        if interview_type == 'technical':
            questions = senior_technical
        elif interview_type == 'behavioral':
            questions = senior_behavioral
        else:  # mixed
            questions = senior_mixed
    
    # Customize questions with role
    customized_questions = []
    for q in questions:
        customized_questions.append(q.replace("{role}", role))
    
    return customized_questions


def generate_ai_feedback(questions_answers, role, experience, interview_type):
    """Generate AI feedback using Mistral AI."""
    try:
        mistral_service = get_mistral_service()
        questions = [qa['question'] for qa in questions_answers]
        candidate_answers = [qa['answer'] for qa in questions_answers]
        feedback = mistral_service.generate_feedback(role, interview_type, questions, candidate_answers)
        return json.dumps(feedback)
    except Exception as e:
        print(f"Error generating feedback: {e}")
        return json.dumps({
            "overall_score": 70,
            "grade_label": "C",
            "summary": "Feedback generation failed.",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "questions": []
        })


class InterviewStartAPIView(APIView):
    def post(self, request):
        serializer = InterviewStartSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            questions = generate_interview_questions(
                data['role'], data['experience'], data['interview_type']
            )
            response_serializer = InterviewStartResponseSerializer({
                'candidate_name': 'Candidate',  # Placeholder
                'role': data['role'],
                'experience': data['experience'],
                'interview_type': data['interview_type'],
                'questions': questions
            })
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InterviewFeedbackAPIView(APIView):
    def post(self, request):
        serializer = InterviewFeedbackSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            feedback = generate_ai_feedback(
                [{'question': q, 'answer': a} for q, a in zip(data['questions'], data['candidate_answers'])],
                data['role'], 3, data['interview_type']  # Default experience
            )
            feedback_data = json.loads(feedback)
            response_serializer = InterviewFeedbackResponseSerializer(feedback_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
