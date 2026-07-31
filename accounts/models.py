import io
from PIL import Image as PilImage

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MaxLengthValidator, URLValidator
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile


ALLOWED_AVATAR_TYPES = {'image/jpeg', 'image/png'}
ALLOWED_AVATAR_EXT = ('.jpg', '.jpeg', '.png')


def validate_avatar(image):
    if hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
        raise ValidationError('Avatar must be under 5MB.')
    ext = image.name.lower()
    if not ext.endswith(ALLOWED_AVATAR_EXT):
        raise ValidationError('Only PNG and JPEG files are allowed.')
    file_obj = getattr(image, 'file', None) or image
    if hasattr(file_obj, 'content_type') and file_obj.content_type not in ALLOWED_AVATAR_TYPES:
        raise ValidationError('Only PNG and JPEG files are allowed.')


class Instrument(models.Model):
    name = models.CharField(max_length=30, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Genre(models.Model):
    name = models.CharField(max_length=30, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    SKILL_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        validators=[validate_avatar],
    )
    display_name = models.CharField(
        max_length=100,
        blank=True,
        validators=[MaxLengthValidator(100)],
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        validators=[MaxLengthValidator(500)],
    )
    instruments = models.ManyToManyField(Instrument, blank=True)
    genres = models.ManyToManyField(Genre, blank=True)
    skill_level = models.CharField(
        max_length=20,
        choices=SKILL_LEVELS,
        default='beginner',
    )
    website = models.URLField(
        max_length=200,
        blank=True,
        validators=[URLValidator()],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

    def __str__(self):
        return self.display_name or self.user.username

    def clean(self):
        if self.display_name and len(self.display_name.strip()) < 2:
            raise ValidationError({'display_name': 'Display name must be at least 2 characters.'})
        if self.bio and len(self.bio.strip()) > 500:
            raise ValidationError({'bio': 'Bio must be under 500 characters.'})

    def get_display_name(self):
        return self.display_name or self.user.username

    def save(self, *args, **kwargs):
        if self.avatar:
            try:
                img = PilImage.open(self.avatar)
                img = img.convert('RGB')
                if img.width > 1024 or img.height > 1024:
                    img.thumbnail((1024, 1024), PilImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85, optimize=True)
                self.avatar.save(self.avatar.name, ContentFile(buf.getvalue()), save=False)
            except Exception:
                pass
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
