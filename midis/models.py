from django.db import models
from django.contrib.auth.models import User


class Midi(models.Model):
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='midis')
    title = models.CharField(max_length=200, blank=True)
    audio = models.FileField(upload_to='midis/audio/')
    instruments = models.CharField(max_length=200, blank=True, default='')
    midi = models.FileField(upload_to='midis/midi/', null=True, blank=True)
    notes_json = models.TextField(blank=True, default='')
    note_count = models.IntegerField(default=0)
    progress = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    duration = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or self.audio.name
