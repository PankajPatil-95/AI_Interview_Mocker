from django.db import models

# Create your models here.
#edited

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    role = models.CharField(max_length=100, blank=True, null=True)
    progress_score = models.FloatField(default=0)

    def __str__(self):
        return self.username

