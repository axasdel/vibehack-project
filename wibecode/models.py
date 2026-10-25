
from django.db import models
from django.contrib.auth.models import User


class ChildProfile(models.Model):
    GENDERS = [
        ("girl", "Девочка"),
        ("boy", "Мальчик"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="child_profile"
    )
    name = models.CharField(max_length=50)
    age = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=10, choices=GENDERS)

    def __str__(self):
        return self.name


class Story(models.Model):
    GENRES = [
        ("fantasy", "Волшебное королевство"),
        ("space", "Космические миры"),
        ("life", "Приключения рядом"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="stories"
    )

    title = models.CharField(max_length=150)
    genre = models.CharField(max_length=20, choices=GENRES)

    # Содержимое всех страниц книги
    pages = models.JSONField(default=list)

    # Варианты выбора для текущей страницы
    options = models.JSONField(default=list)

    # Количество сделанных выборов
    step = models.PositiveSmallIntegerField(default=0)

    is_finished = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
