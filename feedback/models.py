from django.db import models
from django.contrib.auth.models import User

class InterviewResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100)
    experience = models.PositiveSmallIntegerField()
    interview_type = models.CharField(max_length=20, choices=[('technical', 'Technical'), ('behavioral', 'Behavioral'), ('mixed', 'Mixed')], default='mixed')
    mode = models.CharField(max_length=10, choices=[('text', 'Text'), ('voice', 'Voice')])
    webcam_enabled = models.BooleanField(default=False)
    questions = models.JSONField()  # List of questions
    answers = models.JSONField()  # List of answers
    voice_transcripts = models.JSONField(null=True, blank=True)  # For voice mode
    interaction_feedback = models.TextField(null=True, blank=True)  # From webcam analysis
    ai_feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role} Interview"
