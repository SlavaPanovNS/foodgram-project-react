from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Кастомный класс пользователя."""

    email = models.EmailField(
        max_length=254,
        unique=True,
    )
    username = models.CharField(
        max_length=150,
        unique=True,
    )
    first_name = models.CharField(
        max_length=150,
    )
    last_name = models.CharField(
        max_length=150,
    )
    password = models.CharField(
        max_length=150,
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username


class Subscriptions(models.Model):
    """Подписки пользователей друг на друга."""

    author = models.ForeignKey(
        User,
        verbose_name="Автор рецепта",
        related_name="subscribers",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        verbose_name="Подписчики",
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    date_added = models.DateTimeField(
        verbose_name="Дата подписки",
        auto_now_add=True,
        editable=False,
    )

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        constraints = (
            models.UniqueConstraint(
                fields=("author", "user"),
                name="\nRepeat subscription\n",
            ),
            models.CheckConstraint(
                check=~models.Q(author=models.F("user")),
                name="\nNo self sibscription\n",
            ),
        )

    def __str__(self):
        return f"{self.user.username} подписан на {self.author.username}"
