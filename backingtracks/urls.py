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
    path('backingtracks/<int:track_id>/add-to-playlist/', views.add_to_playlist, name='add_to_playlist'),
    path('playlists/add-track/', views.add_to_playlist, name='playlist_add_track'),
    path('backingtracks/<int:track_id>/remove-from-playlist/<int:playlist_id>/', views.remove_from_playlist, name='remove_from_playlist'),
    path('playlists/', views.playlists, name='playlists'),
    path('playlists/new/', views.create_playlist, name='create_playlist'),
    path('playlists/<int:playlist_id>/', views.playlist_detail, name='playlist_detail'),
    path('playlists/<int:playlist_id>/delete/', views.delete_playlist, name='delete_playlist'),
    path('playlists/<int:playlist_id>/edit/', views.edit_playlist, name='edit_playlist'),
]
