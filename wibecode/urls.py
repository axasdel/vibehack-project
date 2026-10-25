from django.urls import path
from . import views

app_name = "wibecode"

urlpatterns = [
    path("", views.auth_page, name="auth"),
    path("home/", views.home, name="home"),
    path("new/", views.new_story, name="new_story"),
    path("books/", views.library, name="library"),
    path("book/<int:story_id>/", views.story_page, name="story"),
    path("logout/", views.logout_page, name="logout"),
]
