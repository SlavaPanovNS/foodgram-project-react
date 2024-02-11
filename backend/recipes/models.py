from django.contrib.auth import get_user_model
from django.db import models

from django.core.validators import MaxValueValidator, MinValueValidator

from colorfield.fields import ColorField


User = get_user_model()

MAX_LENGTH = 200


class Tag(models.Model):
    """Модель Tag."""

    name = models.CharField(
        max_length=MAX_LENGTH, verbose_name="Название", unique=True
    )
    color = ColorField()
    slug = models.SlugField(
        max_length=MAX_LENGTH, null=True, verbose_name="Слаг", unique=True
    )

    class Meta:
        verbose_name = "Тэг"
        verbose_name_plural = "Тэги"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель Ingredient."""

    name = models.CharField(max_length=MAX_LENGTH, verbose_name="Название")
    measurement_unit = models.CharField(
        max_length=MAX_LENGTH, verbose_name="Единицы измерения"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=("measurement_unit", "name"), name="unique_ingredient"
            )
        ]
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"

    def __str__(self):
        return f"{self.name} ({self.measurement_unit})"


class Recipe(models.Model):
    """Модель Recipe."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="Автор",
    )
    name = models.CharField(
        max_length=MAX_LENGTH, verbose_name="Название рецепта"
    )
    image = models.ImageField(
        upload_to="recipes/images/", null=True, default=None
    )
    text = models.TextField(verbose_name="Текст")
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        verbose_name="Ингредиенты",
    )
    tags = models.ManyToManyField(
        Tag,
        through="RecipeTag",
        verbose_name="Тэги",
        related_name="tags",
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name="Время приготовленияв минутах",
        validators=[
            MinValueValidator(
                1, message="Минимальное время приготовления 1 мин."
            ),
            MaxValueValidator(
                1000, message="Максимальное время приготовления 1000 мин."
            ),
        ],
        default=0,
    )

    pub_date = models.DateTimeField(
        verbose_name="Дата публикации", auto_now_add=True, db_index=True
    )

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
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="recipe_ingredient_unique",
            )
        ]


class Favorite(models.Model):
    """Модель избранных рецептов"""

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
        return f"{self.user} - {self.recipe}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "recipe"), name="unique_favorite_user_recipe"
            )
        ]
        verbose_name = "Избранный рецепт"
        verbose_name_plural = "Избранные рецепты"


class RecipeCart(models.Model):
    """Рецепты в корзине покупок."""

    recipe = models.ForeignKey(
        Recipe,
        verbose_name="Рецепты в списке покупок",
        related_name="shopping_cart",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        verbose_name="Владелец списка",
        related_name="shopping_cart",
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
        return f"{self.user} - {self.recipe}"


class RecipeTag(models.Model):
    """Модель связи тега и рецепта."""

    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, verbose_name="Рецепт"
    )
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name="Тег")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "tag"], name="recipe_tag_unique"
            )
        ]

    def __str__(self):
        return f"{self.recipe} - {self.tag}"
