from django.urls import path
from . import views

app_name = 'wibecode'

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('choice/', views.choice, name='choice'),  # <-- Новый маршрут
]
