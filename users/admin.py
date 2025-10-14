
# Register your models here.
from django.contrib import admin
from .models import Profile

admin.site.site_header = "AI Interview Mocker Admin"
admin.site.site_title = "AI Interview Mocker Portal"
admin.site.index_title = "Welcome to AI Interview Mocker Dashboard"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "full_name", "role", "years_experience", "created_at")
	search_fields = ("user__username", "full_name", "role")

