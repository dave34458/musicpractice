from django.contrib import admin
from .models import BackingTrack, Stem, Playlist

@admin.register(BackingTrack)
class BackingTrackAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'artist', 'user', 'status', 'key', 'bpm', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'artist', 'user__username')
    ordering = ('-created_at',)

@admin.register(Stem)
class StemAdmin(admin.ModelAdmin):
    list_display = ('id', 'backing_track', 'name', 'duration')
    search_fields = ('backing_track__title', 'name')

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'created_at')
    search_fields = ('name', 'user__username')
    filter_horizontal = ('tracks',)
