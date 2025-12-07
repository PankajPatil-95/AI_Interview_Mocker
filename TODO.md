# TODO: Remove Raw Media Storage

- [ ] Remove audio_file and video_frames_zip fields from InterviewResult model in feedback/models.py
- [ ] Remove QuestionAudio model entirely from feedback/models.py
- [ ] Create new migration to remove the fields and model
- [ ] Update users/views.py to remove file storage code, keep real-time transcription
- [ ] Check and update any admin or template references
- [ ] Run migrations
- [ ] Test interview flow
- [ ] Update docs if needed
