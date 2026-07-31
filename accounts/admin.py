from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Profile, Instrument, Genre


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_skill_level', 'date_joined')
    list_select_related = ('profile',)

    def get_skill_level(self, obj):
        return obj.profile.skill_level if hasattr(obj, 'profile') else '-'
    get_skill_level.short_description = 'Skill'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Instrument)
admin.site.register(Genre)
