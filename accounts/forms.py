import json
from django import forms
from django.contrib.auth.models import User
from .models import Profile, Instrument, Genre


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'}),
    )
    instruments = forms.CharField(required=False, widget=forms.HiddenInput)
    genres = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Profile
        fields = [
            'avatar', 'display_name', 'bio',
            'skill_level', 'website',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell the world about your music journey\u2026'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://yoursite.com'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
        self.fields['instruments'].initial = json.dumps([i.name for i in self.instance.instruments.all()])
        self.fields['genres'].initial = json.dumps([g.name for g in self.instance.genres.all()])

    def _resolve_tags(self, raw, model):
        try:
            names = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except (json.JSONDecodeError, TypeError):
            return
        names = [n.strip() for n in names if n and n.strip()]
        if len(names) > 10:
            raise forms.ValidationError(f'Maximum 10 {model._meta.verbose_name_plural} allowed.')
        objs = []
        for name in names:
            if len(name) > 30:
                raise forms.ValidationError(f'Each {model._meta.verbose_name} name must be under 30 characters.')
            objs.append(model.objects.get_or_create(name=name)[0])
        return objs

    def clean_instruments(self):
        objs = self._resolve_tags(self.cleaned_data.get('instruments', '[]'), Instrument)
        self._inst_objs = objs
        return self.cleaned_data.get('instruments', '[]')

    def clean_genres(self):
        objs = self._resolve_tags(self.cleaned_data.get('genres', '[]'), Genre)
        self._genre_objs = objs
        return self.cleaned_data.get('genres', '[]')

    def clean_display_name(self):
        name = self.cleaned_data.get('display_name', '').strip()
        if name and len(name) < 2:
            raise forms.ValidationError('Display name must be at least 2 characters.')
        if name and len(name) > 100:
            raise forms.ValidationError('Display name must be under 100 characters.')
        return name

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()
        if bio and len(bio) > 500:
            raise forms.ValidationError('Bio must be under 500 characters.')
        return bio

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data.get('first_name', '')
            self.user.last_name = self.cleaned_data.get('last_name', '')
            if commit:
                self.user.save()
        if commit:
            profile.save()
        if hasattr(self, '_inst_objs') and self._inst_objs is not None:
            profile.instruments.set(self._inst_objs)
        if hasattr(self, '_genre_objs') and self._genre_objs is not None:
            profile.genres.set(self._genre_objs)
        return profile


class ProfileDeleteForm(forms.Form):
    confirm = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Type DELETE to confirm'}),
    )

    def clean_confirm(self):
        value = self.cleaned_data.get('confirm', '').strip()
        if value.upper() != 'DELETE':
            raise forms.ValidationError('Type DELETE exactly to confirm.')
        return value
