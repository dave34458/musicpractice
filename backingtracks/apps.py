from django.apps import AppConfig


class BackingtracksConfig(AppConfig):
    name = 'backingtracks'

    def ready(self):
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return
        from django.db.models import Q
        from .models import BackingTrack
        BackingTrack.objects.filter(
            Q(status='processing') | Q(status='downloading')
        ).update(status='queued')
        from .services import start_worker
        start_worker()
