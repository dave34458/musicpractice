from django.urls import path
from . import views

app_name = 'chordfinder'

urlpatterns = [
    path('chords/', views.search, name='search'),
    path('chords/view/', views.chart_view, name='chart'),
]
