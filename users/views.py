from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, FileResponse, JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Profile
import google.generativeai as genai
import base64
import json
import time

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
        from .gemini_utils import generate_interview_questions
        import random
        random_seed = random.randint(1, 10000)
        
        try:
            print(f"Generating questions for {role} position, {experience} years, type: {interview_type}")
            questions = generate_interview_questions(role, experience, interview_type, random_seed)
            
            if not questions or len(questions) < 5:
                messages.error(request, 'Failed to generate enough interview questions. Please try again.')
                return redirect('dashboard')
            
            print(f"Successfully generated {len(questions)} questions")
            messages.success(request, 'Interview questions generated successfully!')
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating questions: {error_msg}")
            
            if 'quota' in error_msg.lower():
                messages.error(request, 'API quota exceeded. Please try again later.')
            elif 'permission' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                messages.error(request, 'API access error. Please verify your API key.')
            elif 'model' in error_msg.lower() and 'not found' in error_msg.lower():
                messages.error(request, 'AI model configuration error. Please contact support.')
            else:
                messages.error(request, 'An error occurred while generating questions. Please try again.')
            
            return redirect('dashboard')
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
    question_audios = request.session.get('question_audios', {})  # Store per-question audio blobs
    
    # Check if interview data exists
    if not interview_data or not questions:
        messages.error(request, 'No active interview. Please start a new interview.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        audio_blob = request.POST.get('audio_blob', '')
        # Check for uploaded multipart files (preferred over base64 in POST body)
        uploaded_files = request.FILES if hasattr(request, 'FILES') else {}
        uploaded_main_audio = uploaded_files.get('audio_file') if uploaded_files else None
        webcam_frames = request.POST.get('webcam_frames', '[]')
        answer = request.POST.get('answer', '')
        voice_transcripts = request.session.get('voice_transcripts', [])
        interaction_feedbacks = request.session.get('interaction_feedbacks', [])

        from .gemini_utils import analyze_voice_data

        # Capture per-question audio (store each question's audio in session)
        if audio_blob and idx < len(questions):
            question_audios[str(idx)] = audio_blob
            request.session['question_audios'] = question_audios

        # Fast path: just transcribe audio, defer analysis to final feedback
        if audio_blob or uploaded_main_audio:
            try:
                if uploaded_main_audio:
                    # uploaded_main_audio is an InMemoryUploadedFile or TemporaryUploadedFile
                    audio_bytes = uploaded_main_audio.read()
                else:
                    audio_bytes = base64.b64decode(audio_blob.split(',')[1])
                # Use Google Speech-to-Text API for audio transcription
                try:
                    from google.cloud import speech
                    client = speech.SpeechClient()
                    audio = speech.RecognitionAudio(content=audio_bytes)
                    config = speech.RecognitionConfig(
                        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                        sample_rate_hertz=48000,
                        language_code="en-US",
                    )
                    response = client.recognize(config=config, audio=audio)
                    transcript = " ".join([result.alternatives[0].transcript for result in response.results])
                except Exception as import_error:
                    # Detailed logging and fallback chain
                    print(f"Google Speech-to-Text unavailable or failed: {import_error}")
                    transcript = None
                    # Try local Whisper model as a fallback (if installed). Whisper typically
                    # requires ffmpeg to read some container formats (webm). This is optional
                    # and will be attempted only if the package is installed.
                    try:
                        import whisper
                        import tempfile, os
                        # write bytes to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tf:
                            tf.write(audio_bytes)
                            temp_name = tf.name
                        try:
                            model = whisper.load_model('small')
                            wres = model.transcribe(temp_name)
                            transcript = (wres.get('text') or '').strip()
                        finally:
                            try:
                                os.unlink(temp_name)
                            except Exception:
                                pass
                    except Exception as we:
                        # Whisper fallback failed or not available
                        print(f"Whisper fallback unavailable or failed: {we}")
                        transcript = None

                    if not transcript:
                        # Final fallback: use provided text answer if available
                        transcript = answer if answer else "Audio received but transcription unavailable."
                
                voice_transcripts.append({
                    'transcript': transcript,
                    'timestamp': time.time()
                })
                answer = transcript
            except Exception as e:
                voice_transcripts.append({'transcript': "Transcription failed.", 'timestamp': time.time()})
                answer = "Audio submission recorded"
                print(f"Audio transcription error: {e}")

        # Store webcam frames for final analysis (skip per-frame analysis for speed)
        if webcam_frames:
            try:
                frames = json.loads(webcam_frames)
                # Store only first and last frame to reduce processing
                if len(frames) > 2:
                    interaction_feedbacks.append({
                        'frame_count': len(frames),
                        'first_frame': frames[0],
                        'last_frame': frames[-1]
                    })
                else:
                    interaction_feedbacks.append({
                        'frame_count': len(frames),
                        'frames': frames
                    })
            except Exception as e:
                print(f"Webcam frames storage error: {e}")

        # Store answer without per-question analysis (defer to final feedback)
        current_question = questions[idx]
        answers.append({
            'text': answer,
            'question': current_question
        })
        request.session['interview_answers'] = answers
        request.session['voice_transcripts'] = voice_transcripts
        request.session['interaction_feedbacks'] = interaction_feedbacks
        idx += 1
        request.session['current_question_idx'] = idx
        if idx >= len(questions):
            # Generate AI feedback ONCE at the end (not per-question)
            interview_type = interview_data.get('interview_type', 'mixed')
            
            # Merge transcripts from upload-clip endpoint (if available) with answers
            # This ensures we use the real transcriptions instead of fallback text
            question_transcripts = request.session.get('question_transcripts', {})
            merged_answers = []
            for i, ans in enumerate(answers):
                if str(i) in question_transcripts:
                    # Use uploaded transcription if available
                    merged_answers.append({
                        'text': question_transcripts[str(i)],
                        'question': ans['question'],
                        'source': 'transcription'
                    })
                else:
                    # Use fallback answer text
                    merged_answers.append({
                        'text': ans['text'],
                        'question': ans['question'],
                        'source': 'fallback'
                    })
            
            # Build efficient feedback prompt (no per-question analysis calls)
            questions_answers = []
            for i, (q, a) in enumerate(zip(questions, merged_answers), 1):
                questions_answers.append(f"{i}. Q: {q}\n   A: {a['text']}")
            
            qa_text = "\n".join(questions_answers)
            
            # Use fast_model for final feedback generation
            from .gemini_utils import fast_model
            
            feedback_prompt = f"""You are a professional interview evaluator. Analyze the following interview response comprehensively and provide structured feedback.

INTERVIEW DETAILS:
- Position Applied: {interview_data['role']}
- Candidate Experience: {interview_data['experience']} years
- Interview Type: {interview_type.upper()}
- Mode: {mode.upper()}

CANDIDATE RESPONSES:
{qa_text}

INSTRUCTIONS:
1. Evaluate each response on depth, accuracy, clarity, and relevance
2. Identify key strengths and areas needing improvement
3. Provide actionable, professional suggestions
4. Score each answer from 0-100 based on relevance and quality
5. Return ONLY valid JSON with no markdown formatting or extra text

Return this exact JSON structure:
{{
  "overall_score": <integer 0-100>,
  "grade_label": "<A|B|C|D|F>",
  "summary": "<Professional 2-3 sentence summary of overall performance>",
  "strengths": [
    "<Specific strength 1>",
    "<Specific strength 2>",
    "<Specific strength 3>"
  ],
  "weaknesses": [
    "<Area for improvement 1>",
    "<Area for improvement 2>",
    "<Area for improvement 3>"
  ],
  "suggestions": [
    "<Actionable suggestion 1>",
    "<Actionable suggestion 2>",
    "<Actionable suggestion 3>"
  ],
  "questions": [
    {{
      "id": "1",
      "question": "<Full question text>",
      "answer": "<Candidate's answer>",
      "score": <0-100>,
      "feedback": "<Professional feedback on this answer>"
    }}
  ]
}}"""
            
            # Build a professional default feedback structure (fallback)
            default_questions_feedback = []
            for i, (q, a) in enumerate(zip(questions, answers), 1):
                default_questions_feedback.append({
                    "id": str(i),
                    "question": q,
                    "answer": a['text'][:200],
                    "score": 65,
                    "feedback": "Response was adequate. For improvement, consider adding more specific examples and demonstrating deeper technical knowledge."
                })
            
            ai_feedback = json.dumps({
                "overall_score": 65,
                "grade_label": "C",
                "summary": f"Interview assessment for {interview_data['role']} position. Candidate demonstrated foundational knowledge with room for improvement in technical depth and communication clarity.",
                "strengths": [
                    "Participated fully in the interview",
                    "Provided responses to all questions",
                    "Demonstrated willingness to engage with technical topics"
                ],
                "weaknesses": [
                    "Limited specific examples and case studies in responses",
                    "Could improve depth of technical knowledge",
                    "More structured communication would enhance responses"
                ],
                "suggestions": [
                    "Prepare specific project examples demonstrating your expertise",
                    "Study core concepts relevant to the {interview_data['role']} role",
                    "Practice articulating technical concepts clearly and concisely"
                ],
                "questions": default_questions_feedback
            })
            
            try:
                if fast_model:
                    # Optimized generation config for professional feedback
                    response = fast_model.generate_content(
                        feedback_prompt,
                        generation_config={
                            'temperature': 0.7,
                            'max_output_tokens': 3000,
                            'top_p': 0.95,
                            'top_k': 40
                        }
                    )
                    feedback_text = response.text.strip()
                    
                    # Extract JSON (handle markdown code blocks)
                    if '```json' in feedback_text:
                        feedback_text = feedback_text.split('```json')[1].split('```')[0].strip()
                    elif '```' in feedback_text:
                        feedback_text = feedback_text.split('```')[1].split('```')[0].strip()
                    
                    try:
                        parsed_feedback = json.loads(feedback_text)
                        ai_feedback = json.dumps(parsed_feedback)
                    except json.JSONDecodeError as je:
                        print(f"JSON parse error: {str(je)[:100]}")
                        ai_feedback = json.dumps({
                            "overall_score": 60,
                            "grade_label": "Fair",
                            "summary": "Interview completed with analysis.",
                            "strengths": ["Completed interview successfully"],
                            "weaknesses": ["Detailed feedback parsing failed"],
                            "suggestions": ["Review feedback format"],
                            "questions": []
                        })
            except Exception as e:
                print(f"Feedback generation error: {str(e)[:100]}")
                ai_feedback = json.dumps({
                    "overall_score": 55,
                    "grade_label": "Fair",
                    "summary": "Interview completed.",
                    "strengths": ["Completed interview"],
                    "weaknesses": ["Feedback generation error"],
                    "suggestions": ["Try again"],
                    "questions": []
                })
            
            # Store interaction feedback metadata (not detailed frame analysis)
            interaction_feedback_str = json.dumps({
                'frame_analysis': interaction_feedbacks,
                'voice_transcripts': voice_transcripts
            })
            
            from feedback.models import InterviewResult

            result = InterviewResult.objects.create(
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
                interaction_feedback=interaction_feedback_str,
                ai_feedback=ai_feedback
            )





            # Attempt to parse AI feedback and compute a human-friendly grade using feedback_utils
            try:
                from users.feedback_utils import render_feedback_context, compute_grade_label
                parsed = render_feedback_context(ai_feedback)
                raw_score = parsed.get('overall_score', 0) or 0
                try:
                    raw_score_int = int(raw_score)
                except Exception:
                    raw_score_int = 0
                # If the model returned a 1-10 scale, rescale to 0-100
                if 0 <= raw_score_int <= 10:
                    scaled_score = raw_score_int * 10
                else:
                    scaled_score = raw_score_int
                grade_label = parsed.get('grade_label') or compute_grade_label(scaled_score)
            except Exception as e:
                print(f"Feedback parsing error: {e}")
                scaled_score = None
                grade_label = 'Unrated'

            # Save parsed score/label to the InterviewResult
            try:
                if scaled_score is not None:
                    result.overall_score = int(scaled_score)
                result.grade_label = grade_label
                result.save()
            except Exception as e:
                print(f"Error saving score/label to InterviewResult: {e}")

            # Inform the user and redirect to the feedback (detail) page
            if scaled_score is not None:
                messages.success(request, f'Interview completed — Score: {scaled_score} ({grade_label}). Results saved.')
            else:
                messages.success(request, 'Interview completed! Results saved. (Score unavailable)')

            # clear session data for the interview
            del request.session['interview_questions']
            del request.session['current_question_idx']
            del request.session['interview_answers']
            del request.session['voice_transcripts']
            del request.session['interaction_feedbacks']
            del request.session['interview_data']
            if 'question_audios' in request.session:
                del request.session['question_audios']

            # Redirect to the per-interview feedback/detail page
            return redirect('result_detail', pk=result.id)
        return redirect('interview_run')
    if not questions or idx >= len(questions):
        return redirect('dashboard')
    
    question = questions[idx]
    pure_voice = interview_data.get('pure_voice', False)
    
    # Ensure all required context is available
    context = {
        'question': question,
        'current_idx': idx,
        'total': len(questions),
        'mode': mode,
        'webcam_enabled': webcam_enabled,
        'pure_voice': pure_voice
    }
    
    return render(request, 'interview_run.html', context)

@login_required
def results_view(request):
    from feedback.models import InterviewResult
    results = InterviewResult.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'results.html', {'results': results})


@login_required
def result_detail_view(request, pk):
    """Show detailed feedback for a single InterviewResult.

    Staff users may view any result; regular users only their own results.
    """
    from feedback.models import InterviewResult
    from users.feedback_utils import render_feedback_context

    try:
        result = InterviewResult.objects.get(pk=pk, user=request.user)
    except InterviewResult.DoesNotExist:
        # allow staff to view any result
        if request.user.is_staff:
            result = get_object_or_404(InterviewResult, pk=pk)
        else:
            messages.error(request, 'Requested feedback not found.')
            return redirect('results')

    parsed = render_feedback_context(result.ai_feedback)

    context = {
        'result': result,
        'feedback': parsed,
    }
    return render(request, 'result_detail.html', context)


@login_required
def upload_question_clip(request):
    """
    Accept per-question audio clip immediately after candidate answers a question.
    
    Expected multipart POST with:
    - question_idx: integer index of the question (0-based)
    - audio_file: binary audio blob
    
    Transcribe immediately and return JSON with transcription status.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        question_idx = int(request.POST.get('question_idx', -1))
        audio_file = request.FILES.get('audio_file')
        
        if not audio_file or question_idx < 0:
            return JsonResponse({'error': 'Missing audio_file or question_idx'}, status=400)
        
        # Read audio bytes
        audio_bytes = audio_file.read()
        
        # Store clip in session for later save (when interview completes)
        if 'question_audio_clips' not in request.session:
            request.session['question_audio_clips'] = {}
        
        # Store file object for later use (we'll save it in interview_run_view at completion)
        request.session['question_audio_clips'][str(question_idx)] = {
            'filename': audio_file.name,
            'content_type': audio_file.content_type
        }
        
        # Attempt transcription immediately
        transcript = "Audio received"
        try:
            # Try Whisper first (local, no authentication required)
            transcript = None
            try:
                import whisper
                import tempfile
                import os
                
                # Write audio bytes to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tf:
                    tf.write(audio_bytes)
                    temp_name = tf.name
                
                try:
                    print(f"Loading Whisper model for Q{question_idx+1}...")
                    model = whisper.load_model('base')  # Use 'base' for faster inference
                    print(f"Transcribing Q{question_idx+1} audio...")
                    result_whisper = model.transcribe(temp_name, language='en')
                    transcript = (result_whisper.get('text') or '').strip()
                    print(f"Q{question_idx+1} Whisper transcription: {transcript[:100]}...")
                finally:
                    try:
                        os.unlink(temp_name)
                    except:
                        pass
            except Exception as whisper_err:
                print(f"Q{question_idx+1} Whisper transcription failed: {whisper_err}")
                
                # Fallback: Try Google Cloud Speech-to-Text
                if not transcript:
                    try:
                        from google.cloud import speech
                        print(f"Attempting Google STT for Q{question_idx+1}...")
                        client = speech.SpeechClient()
                        audio = speech.RecognitionAudio(content=audio_bytes)
                        config = speech.RecognitionConfig(
                            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                            sample_rate_hertz=48000,
                            language_code="en-US",
                        )
                        response = client.recognize(config=config, audio=audio)
                        transcript = " ".join([result.alternatives[0].transcript for result in response.results])
                        print(f"Q{question_idx+1} Google STT transcription: {transcript[:100]}...")
                    except Exception as goog_err:
                        print(f"Q{question_idx+1} Google STT failed: {goog_err}")
            
            # Final fallback if both failed
            if not transcript:
                print(f"Q{question_idx+1}: Using fallback placeholder transcription")
                transcript = "Audio received but automatic transcription unavailable. Please provide text answer."
        except Exception as e:
            print(f"Q{question_idx+1} Transcription error (outer): {e}")
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
    """Protected media download: only staff (admin) can download stored audio/video files.

    kind: 'audio' or 'frames'
    """
    from feedback.models import InterviewResult
    result = get_object_or_404(InterviewResult, pk=pk)
    # Only admins (staff) may access media
    if not request.user.is_staff:
        raise Http404()

    if kind == 'audio' and result.audio_file:
        return FileResponse(result.audio_file.open('rb'), as_attachment=True, filename=result.audio_file.name.split('/')[-1])
    if kind == 'frames' and result.video_frames_zip:
        return FileResponse(result.video_frames_zip.open('rb'), as_attachment=True, filename=result.video_frames_zip.name.split('/')[-1])
    raise Http404()

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
