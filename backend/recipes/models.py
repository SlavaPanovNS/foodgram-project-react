from typing import Optional

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Exists, OuterRef

User = get_user_model()


class Tag(models.Model):
    """Тэги."""

    # Отображается в UI
    name = models.CharField(
        max_length=200, verbose_name="Название", unique=True
    )
    color = models.CharField(
        max_length=200, null=True, verbose_name="Цвет", unique=True
    )
    slug = models.SlugField(
        max_length=200, null=True, verbose_name="Слаг", unique=True
    )

    class Meta:
        verbose_name = "Тэг"
        verbose_name_plural = "Тэги"

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название")
    measurement_unit = models.CharField(
        max_length=200, verbose_name="Единицы измерения"
    )

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"

    def __str__(self):
        return f"{self.name} ({self.measurement_unit})"


class RecipeQuerySet(models.QuerySet):
    def add_user_annotations(self, user_id: Optional[int]):
        return self.annotate(
            is_favorite=Exists(
                Favorite.objects.filter(
                    user_id=user_id, recipe__pk=OuterRef("pk")
                )
            ),
        )


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="Автор",
    )
    name = models.CharField(max_length=200, verbose_name="Название рецепта")
    image = models.ImageField(
        upload_to="recipes/images/", null=True, default=None
    )
    text = models.TextField(verbose_name="Текст")
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        through_fields=("recipe", "ingredient"),
        verbose_name="Ингредиенты",
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name="Тэги",
        related_name="recipes",
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name="Время приготовленияв минутах",
        default=0,
    )

    pub_date = models.DateTimeField(
        verbose_name="Дата публикации", auto_now_add=True, db_index=True
    )

    objects = RecipeQuerySet.as_manager()

    class Meta:
        ordering = ("-pub_date",)
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Модель соединяющая Recipe и Ingredient"""

    amount = models.PositiveIntegerField(verbose_name="Количество")
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, verbose_name="Рецепт"
    )

    def __str__(self):
        return f"{self.ingredient} в {self.recipe}"

    class Meta:
        verbose_name = "Ингредиент в рецепте"
        verbose_name_plural = "Ингредиенты в рецептах"


class Favorite(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Рецепт",
    )

    def __str__(self):
        return f"Избранный {self.recipe} у {self.user}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "recipe"), name="unique_favorite_user_recipe"
            )
        ]
        verbose_name = "Объект избранного"
        verbose_name_plural = "Объекты избранного"


class RecipeCart(models.Model):
    """Рецепты в корзине покупок."""

    recipe = models.ForeignKey(
        Recipe,
        verbose_name="Рецепты в списке покупок",
        related_name="in_carts",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        verbose_name="Владелец списка",
        related_name="carts",
        on_delete=models.CASCADE,
    )
    date_added = models.DateTimeField(
        verbose_name="Дата добавления", auto_now_add=True, editable=False
    )

    class Meta:
        verbose_name = "Рецепт в списке покупок"
        verbose_name_plural = "Рецепты в списке покупок"
        constraints = (
            models.UniqueConstraint(
                fields=(
                    "recipe",
                    "user",
                ),
                name="\n%(app_label)s_%(class)s recipe is cart alredy\n",
            ),
        )

    def __str__(self):
        return self.recipe.name
