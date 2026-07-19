from django.db import models
from django.contrib.auth.models import User

class BackingTrack(models.Model):
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('downloading', 'Downloading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backingtracks')
    youtube_url = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    artist = models.CharField(max_length=200, blank=True)
    bpm = models.FloatField(null=True, blank=True)
    key = models.CharField(max_length=20, blank=True, default='')
    duration = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to='track_images/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or self.youtube_url

class Stem(models.Model):
    backing_track = models.ForeignKey(BackingTrack, on_delete=models.CASCADE, related_name='stems')
    name = models.CharField(max_length=20)
    audio_file = models.FileField(upload_to='stems/')
    duration = models.FloatField(default=0)

    class Meta:
        unique_together = ['backing_track', 'name']

    def __str__(self):
        return f"{self.backing_track.title} - {self.name}"

    def filename(self):
        import os
        return os.path.basename(self.audio_file.name)

class Playlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    image = models.ImageField(upload_to='playlist_images/', null=True, blank=True)
    tracks = models.ManyToManyField(BackingTrack, related_name='playlists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
