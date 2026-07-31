from django.urls import path
from . import views

app_name = 'chordfinder'

urlpatterns = [
    path('chords/', views.search, name='search'),
    path('chords/search.json', views.search_json, name='search_json'),
    path('chords/view/', views.chart_view, name='chart'),
]
