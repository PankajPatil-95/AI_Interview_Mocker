from django.contrib import admin
from .models import InterviewResult

@admin.register(InterviewResult)
class InterviewResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'role', 'interview_type', 'overall_score', 'created_at')
    list_filter = ('interview_type', 'mode', 'webcam_enabled', 'created_at')
    search_fields = ('user__username', 'name', 'role')
    readonly_fields = ('created_at', 'questions', 'answers', 'voice_transcripts', 'ai_feedback')
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'name', 'role', 'experience', 'created_at')
        }),
        ('Interview Details', {
            'fields': ('interview_type', 'mode', 'webcam_enabled')
        }),
        ('Questions & Answers', {
            'fields': ('questions', 'answers', 'voice_transcripts'),
            'classes': ('collapse',)
        }),
        ('Feedback & Scoring', {
            'fields': ('ai_feedback', 'interaction_feedback', 'overall_score', 'grade_label')
        }),
    )
