from django.urls import path
from . import views

app_name = 'midis'

urlpatterns = [
    path('midis/', views.index, name='index'),
    path('midis/<int:midi_id>/', views.detail, name='detail'),
    path('midis/<int:midi_id>/status/', views.status, name='status'),
    path('midis/<int:midi_id>/notes/', views.notes, name='notes'),
    path('midis/<int:midi_id>/download/', views.download, name='download'),
    path('midis/<int:midi_id>/delete/', views.delete, name='delete'),
]
