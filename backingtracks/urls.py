from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('backingtracks/', views.backingtracks_list, name='backingtracks'),
    path('backingtracks/new/', views.new_track, name='new_track'),
    path('backingtracks/<int:track_id>/', views.track_player, name='track_player'),
    path('backingtracks/<int:track_id>/status/', views.track_status, name='track_status'),
    path('backingtracks/<int:track_id>/edit/', views.edit_track, name='track_edit'),
    path('backingtracks/<int:track_id>/delete/', views.delete_track, name='delete_track'),
]
