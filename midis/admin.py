from django.contrib import admin
from .models import Midi


@admin.register(Midi)
class MidiAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'status', 'note_count', 'progress', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = ('id',)