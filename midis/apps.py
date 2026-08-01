import os

from django.apps import AppConfig
from django.db import ProgrammingError, OperationalError


class MidisConfig(AppConfig):
    name = 'midis'

    def ready(self):
        try:
            if not os.environ.get('MIDIS_NO_WORKER'):
                from .models import Midi
                Midi.objects.filter(status='processing').update(status='queued')
                from .services import start_worker
                start_worker()
        except (ProgrammingError, OperationalError):
            pass
