from django.urls import path
from .views import home, login_view, signup_view, logout_view, dashboard, faq, testimonial, profile_view, profile_edit, mock_interview_view, interview_run_view, results_view, stats_view, feature_mock_interviews, feature_feedback, feature_tips

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit, name='profile_edit'),
    path('faq/', faq, name='faq'),
    path('testimonial/', testimonial, name='testimonial'),
    path('mock-interview/', mock_interview_view, name='mock_interview'),
    path('interview-run/', interview_run_view, name='interview_run'),
    path('results/', results_view, name='results'),
    path('stats/', stats_view, name='stats'),
    path('features/mock-interviews/', feature_mock_interviews, name='feature_mock_interviews'),
    path('features/feedback/', feature_feedback, name='feature_feedback'),
    path('features/tips/', feature_tips, name='feature_tips'),
]
