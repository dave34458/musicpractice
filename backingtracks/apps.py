from django.apps import AppConfig
from django.db import ProgrammingError, OperationalError


class BackingtracksConfig(AppConfig):
    name = 'backingtracks'

    def ready(self):
        try:
            from django.db.models import Q
            from .models import BackingTrack
            BackingTrack.objects.filter(
                Q(status='processing') | Q(status='downloading')
            ).update(status='queued')
            from .services import start_worker
            start_worker()
        except (ProgrammingError, OperationalError):
            pass
