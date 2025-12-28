from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "email"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "first_name", "email", "password"]

    def create(self, validated_data):
        username = validated_data.get("username")
        email = validated_data.get("email", "")
        first_name = validated_data.get("first_name", "")
        password = validated_data.get("password")
        user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
        return user


class InterviewQuestionSerializer(serializers.Serializer):
    """Serializer for interview questions response."""
    questions = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of generated interview questions"
    )


class AudioTranscriptionSerializer(serializers.Serializer):
    """Serializer for audio transcription response."""
    transcript = serializers.CharField(help_text="Transcribed text from audio")


class AIFeedbackSerializer(serializers.Serializer):
    """Serializer for AI feedback response."""
    overall_score = serializers.IntegerField(min_value=0, max_value=100)
    grade_label = serializers.CharField(max_length=1)
    summary = serializers.CharField()
    strengths = serializers.ListField(child=serializers.CharField())
    weaknesses = serializers.ListField(child=serializers.CharField())
    suggestions = serializers.ListField(child=serializers.CharField())
    questions = serializers.ListField(
        child=serializers.DictField()
    )


class InterviewStartSerializer(serializers.Serializer):
    """Serializer for interview start request."""
    name = serializers.CharField(max_length=100)
    role = serializers.CharField(max_length=100)
    experience = serializers.ChoiceField(choices=['Fresher', 'Mid', 'Senior'])
    interview_type = serializers.ChoiceField(choices=['technical', 'behavioural', 'mixed'])


class InterviewStartResponseSerializer(serializers.Serializer):
    """Serializer for interview start response."""
    candidate_name = serializers.CharField()
    role = serializers.CharField()
    experience = serializers.CharField()
    interview_type = serializers.CharField()
    questions = serializers.ListField(child=serializers.CharField())


class InterviewFeedbackSerializer(serializers.Serializer):
    """Serializer for interview feedback request."""
    role = serializers.CharField(max_length=100)
    interview_type = serializers.CharField(max_length=50)
    questions = serializers.ListField(child=serializers.CharField())
    candidate_answers = serializers.ListField(child=serializers.CharField())


class InterviewFeedbackResponseSerializer(serializers.Serializer):
    """Serializer for interview feedback response."""
    overall_score = serializers.IntegerField(min_value=0, max_value=10)
    technical_knowledge = serializers.CharField()
    communication_skills = serializers.CharField()
    problem_solving = serializers.CharField()
    strengths = serializers.ListField(child=serializers.CharField())
    weaknesses = serializers.ListField(child=serializers.CharField())
    suggestions = serializers.ListField(child=serializers.CharField())
    recommendation = serializers.CharField()
