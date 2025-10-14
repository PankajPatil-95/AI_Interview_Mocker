from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Profile
import google.generativeai as genai
import base64
import json

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
        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.full_name = name
            profile.role = role
            profile.years_experience = int(experience)
            profile.save()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        type_desc = {
            'technical': 'technical skills and problem-solving',
            'behavioral': 'behavioral and situational questions',
            'mixed': 'technical and behavioral questions'
        }
        import random
        random_seed = random.randint(1, 10000)
        prompt = f"Generate 10 unique and varied interview questions for a {role} with {experience} years of experience. Focus on {type_desc.get(interview_type, 'technical and behavioral questions')}. Make them different each time. Random seed: {random_seed}. Return as a numbered list."
        try:
            response = model.generate_content(prompt)
            questions_text = response.text.strip()
            import re
            questions = re.split(r'\d+\.\s*', questions_text)[1:]  # Skip first empty
            questions = [q.strip() for q in questions if q.strip()]
            if len(questions) < 5:
                questions = ["What is your greatest strength?", "Describe a challenge you faced.", "Why do you want this job?", "How do you handle stress?", "Tell me about a time you showed leadership."]
        except Exception as e:
            questions = ["What is your greatest strength?", "Describe a challenge you faced.", "Why do you want this job?", "How do you handle stress?", "Tell me about a time you showed leadership."]
        request.session['interview_questions'] = questions
        request.session['current_question_idx'] = 0
        request.session['interview_answers'] = []
        request.session['voice_transcripts'] = []
        request.session['interaction_feedbacks'] = []
        request.session['interview_data'] = {'name': name, 'role': role, 'experience': experience, 'interview_type': interview_type, 'mode': mode, 'webcam_enabled': webcam_enabled, 'pure_voice': mode == 'voice'}
        return redirect('interview_run')
    return redirect('dashboard')

@login_required
def interview_run_view(request):
    questions = request.session.get('interview_questions', [])
    idx = request.session.get('current_question_idx', 0)
    answers = request.session.get('interview_answers', [])
    interview_data = request.session.get('interview_data', {})
    mode = interview_data.get('mode', 'text')
    webcam_enabled = interview_data.get('webcam_enabled', False)
    if request.method == 'POST':
        audio_blob = request.POST.get('audio_blob', '')
        webcam_frames = request.POST.get('webcam_frames', '[]')
        answer = request.POST.get('answer', '')
        voice_transcripts = request.session.get('voice_transcripts', [])
        interaction_feedbacks = request.session.get('interaction_feedbacks', [])

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        if audio_blob:
            try:
                audio_bytes = base64.b64decode(audio_blob.split(',')[1])
                audio_file = genai.upload_file(data=audio_bytes, mime_type='audio/webm')
                transcript_prompt = "Transcribe this audio accurately."
                transcript_response = model.generate_content([audio_file, transcript_prompt])
                transcript = transcript_response.text.strip()
                voice_transcripts.append(transcript)
                answer = transcript
            except Exception as e:
                voice_transcripts.append("Transcription failed.")
                print(f"Audio transcription error: {e}")

        if webcam_frames:
            try:
                frames = json.loads(webcam_frames)
                image_files = []
                for frame in frames:
                    img_bytes = base64.b64decode(frame.split(',')[1])
                    image_file = genai.upload_file(data=img_bytes, mime_type='image/jpeg')
                    image_files.append(image_file)
                confidence_prompt = "Analyze these images for interview confidence: eye contact, posture, smiles, overall confidence level. Provide a summary."
                confidence_response = model.generate_content(image_files + [confidence_prompt])
                feedback = confidence_response.text.strip()
                interaction_feedbacks.append(feedback)
            except Exception as e:
                interaction_feedbacks.append("Confidence analysis failed.")
                print(f"Webcam analysis error: {e}")

        answers.append(answer)
        request.session['interview_answers'] = answers
        request.session['voice_transcripts'] = voice_transcripts
        request.session['interaction_feedbacks'] = interaction_feedbacks
        idx += 1
        request.session['current_question_idx'] = idx
        if idx >= len(questions):
            # Generate AI feedback and save to model
            interview_type = interview_data.get('interview_type', 'mixed')
            feedback_prompt = f"Analyze the following {interview_type} interview for a {interview_data['role']} with {interview_data['experience']} years experience. Mode: {mode}. Webcam: {webcam_enabled}. Questions: {questions}. Answers: {answers}. Voice Transcripts: {voice_transcripts}. Interaction Feedback: {interaction_feedbacks}. Provide detailed personalized feedback on strengths, weaknesses, voice quality, confidence, and suggestions for improvement."
            try:
                feedback_response = model.generate_content(feedback_prompt)
                ai_feedback = feedback_response.text.strip()
            except Exception as e:
                ai_feedback = "Feedback generation failed."
                print(f"Feedback generation error: {e}")
            from feedback.models import InterviewResult
            InterviewResult.objects.create(
                user=request.user,
                name=interview_data['name'],
                role=interview_data['role'],
                experience=int(interview_data['experience']),
                interview_type=interview_type,
                mode=mode,
                webcam_enabled=webcam_enabled,
                questions=questions,
                answers=answers,
                voice_transcripts=voice_transcripts,
                interaction_feedback='; '.join(interaction_feedbacks),
                ai_feedback=ai_feedback
            )
            messages.success(request, 'Interview completed! Results saved.')
            del request.session['interview_questions']
            del request.session['current_question_idx']
            del request.session['interview_answers']
            del request.session['voice_transcripts']
            del request.session['interaction_feedbacks']
            del request.session['interview_data']
            return redirect('dashboard')
        return redirect('interview_run')
    if not questions or idx >= len(questions):
        return redirect('dashboard')
    question = questions[idx]
    pure_voice = interview_data.get('pure_voice', False)
    return render(request, 'interview_run.html', {'question': question, 'current_idx': idx, 'total': len(questions), 'mode': mode, 'webcam_enabled': webcam_enabled, 'pure_voice': pure_voice})

@login_required
def results_view(request):
    from feedback.models import InterviewResult
    results = InterviewResult.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'results.html', {'results': results})

from django.http import JsonResponse

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
