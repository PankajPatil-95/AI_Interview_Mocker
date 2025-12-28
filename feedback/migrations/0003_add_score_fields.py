from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0002_interviewresult_interview_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewresult',
            name='overall_score',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='interviewresult',
            name='grade_label',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
    ]
