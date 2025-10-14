


# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
	"""Extended profile for signup details linked to Django's User."""
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	full_name = models.CharField(max_length=150, blank=True)
	role = models.CharField(max_length=100, blank=True)
	years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

	def __str__(self):
		return self.full_name or self.user.username


class Testimonial(models.Model):
    """Model for user testimonials displayed on the landing page."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Testimonial by {self.user.first_name} {self.user.last_name}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
	if created:
		Profile.objects.create(user=instance)

