#!-*-coding:utf-8-*-
import base64  # Модуль с функциями кодирования и декодирования base64

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

# from rest_framework.exceptions import ValidationError

# # from rest_framework.status import HTTP_400_BAD_REQUEST
# from django.shortcuts import get_object_or_404


from recipes.models import (
    Ingredient,
    RecipeIngredient,
    Recipe,
    Tag,
    RecipeCart,
    Favorite,
    RecipeTag,
)
from users.models import Subscriptions

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name="temp." + ext)

        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для User."""

    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def get_is_subscribed(self, obj):
        user = self.context.get("request").user

        if user.is_anonymous or (user == obj):
            return False

        return Subscriptions.objects.filter(user=user, author=obj).exists()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"


class RecipeIngredientSerializer(serializers.ModelSerializer):
    # name = serializers.StringRelatedField(source="ingredient.name")
    # measurement_unit = serializers.StringRelatedField(
    #     source="ingredient.measurement_unit"
    # )
    # id = serializers.PrimaryKeyRelatedField(
    #     source="ingredient", queryset=Ingredient.objects.all()
    # )

    # class Meta:
    #     model = RecipeIngredient
    #     fields = ("amount", "name", "measurement_unit", "id")
    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(
        source="ingredient.measurement_unit"
    )

    class Meta:
        model = RecipeIngredient
        fields = ["id", "name", "amount", "measurement_unit"]


class RecipeListSerializer(serializers.ModelSerializer):
    """Получение списка рецептов."""

    tags = TagSerializer(many=True)
    # tags = serializers.PrimaryKeyRelatedField(
    #     many=True, queryset=Tag.objects.all()
    # )
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField(
        method_name="get_is_favorited"
    )
    is_in_shopping_cart = serializers.SerializerMethodField(
        method_name="get_is_in_shopping_cart"
    )

    class Meta:
        model = Recipe
        fields = [
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        ]

    def get_ingredients(self, recipe):
        ingredients = RecipeIngredient.objects.filter(recipe=recipe)
        return RecipeIngredientSerializer(ingredients, many=True).data

    def get_is_favorited(self, recipe):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return Favorite.objects.filter(
            user=request.user, recipe_id=recipe
        ).exists()

    def get_is_in_shopping_cart(self, recipe):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return RecipeCart.objects.filter(
            user=request.user, recipe_id=recipe
        ).exists()


class IngredientCreateInRecipeSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(read_only=True)
    id = serializers.PrimaryKeyRelatedField(
        source="ingredient", queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField(write_only=True, min_value=1)

    class Meta:
        model = RecipeIngredient
        fields = ("recipe", "id", "amount")

    # id = serializers.IntegerField()
    # amount = serializers.IntegerField()

    # class Meta:
    #     model = RecipeIngredient
    #     fields = ["id", "amount"]


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all()
    )
    ingredients = IngredientCreateInRecipeSerializer(many=True)
    author = UserSerializer(read_only=True)
    image = Base64ImageField(required=False, allow_null=True)

    def validate_ingredients(self, value):
        if len(value) < 1:
            raise serializers.ValidationError(
                "Добавьте хотя бы один ингредиент."
            )
        return value

    def create_ingredients(self, ingredients, recipe):
        for i in ingredients:
            ingredient = Ingredient.objects.get(id=i["id"])
            RecipeIngredient.objects.create(
                ingredient=ingredient, recipe=recipe, amount=i["amount"]
            )

    def create_tags(self, tags, recipe):
        for tag in tags:
            RecipeTag.objects.create(recipe=recipe, tag=tag)

    def create(self, validated_data):

        ingredients = validated_data.pop("ingredients")
        tags = validated_data.pop("tags")
        author = self.context.get("request").user
        recipe = Recipe.objects.create(author=author, **validated_data)
        create_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient["ingredient"],
                amount=ingredient["amount"],
            )
            for ingredient in ingredients
        ]
        RecipeIngredient.objects.bulk_create(create_ingredients)
        self.create_tags(tags, recipe)
        return recipe

    # def create(self, validated_data):
    #     ingredients = validated_data.pop("ingredients")
    #     tags = validated_data.pop("tags")
    #     author = self.context.get("request").user
    #     recipe = Recipe.objects.create(author=author, **validated_data)

    # create_ingredients = [
    #     RecipeIngredient(
    #         recipe=recipe,
    #         ingredient=ingredient["ingredient"],
    #         amount=ingredient["amount"],
    #     )
    #     for ingredient in ingredients
    #     ]
    #     RecipeIngredient.objects.bulk_create(create_ingredients)
    #     recipe.tags.set(tags)
    #     return recipe
    def update(self, instance, validated_data):
        ingredients = validated_data.pop("ingredients", None)
        if ingredients is not None:
            instance.ingredients.clear()

            create_ingredients = [
                RecipeIngredient(
                    recipe=instance,
                    ingredient=ingredient["ingredient"],
                    amount=ingredient["amount"],
                )
                for ingredient in ingredients
            ]
            RecipeIngredient.objects.bulk_create(create_ingredients)
        if validated_data.get("image"):
            instance.image = validated_data.get("image", instance.image)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return RecipeListSerializer(
            instance, context={"request": self.context.get("request")}
        ).data

    # def update(self, instance, validated_data):
    #     ingredients = validated_data.pop("ingredients", None)
    #     if ingredients is not None:
    #         instance.ingredients.clear()

    #         create_ingredients = [
    #             RecipeIngredient(
    #                 recipe=instance,
    #                 ingredient=ingredient["ingredient"],
    #                 amount=ingredient["amount"],
    #             )
    #             for ingredient in ingredients
    #         ]
    #         RecipeIngredient.objects.bulk_create(create_ingredients)
    #     instance.image = validated_data.get("image", instance.image)

    #     return super().update(instance, validated_data)

    # def to_representation(self, obj):
    #     """Возвращаем прдеставление в таком же виде, как и GET-запрос."""
    #     self.fields.pop("ingredients")
    #     representation = super().to_representation(obj)
    #     representation["ingredients"] = RecipeIngredientSerializer(
    #         RecipeIngredient.objects.filter(recipe=obj).all(), many=True
    #     ).data
    #     return representation

    class Meta:
        model = Recipe
        fields = (
            "id",
            "author",
            "ingredients",
            "tags",
            "image",
            "name",
            "text",
            "cooking_time",
        )


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class RecipeShortSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")


# class SubscriptionsListSerializer(serializers.ModelSerializer):
#     """Сериализатор для отображения подписок пользователя."""

#     is_subscribed = serializers.SerializerMethodField()
#     recipes = serializers.SerializerMethodField()
#     recipes_count = serializers.SerializerMethodField()

#     class Meta:
#         model = User
#         fields = (
#             [
#                 "id",
#                 "email",
#                 "username",
#                 "first_name",
#                 "last_name",
#                 "is_subscribed",
#                 "recipes",
#                 "recipes_count",
#             ],
#         )
#         read_only_fields = ("email", "username", "first_name", "last_name")

#     def get_is_subscribed(self, obj):
#         request = self.context.get("request")
#         if request is None or request.user.is_anonymous:
#             return False
#         return Subscriptions.objects.filter(
#             user=request.user, author=obj
#         ).exists()

#     def get_recipes(self, obj):
#         request = self.context.get("request")
#         if not request or request.user.is_anonymous:
#             return False
#         recipes = Recipe.objects.filter(author=obj)
#         limit = request.query_params.get("recipes_limit")
#         if limit:
#             recipes = recipes[: int(limit)]
#         return FavoriteListSerializer(
#             recipes, many=True, context={"request": request}
#         ).data

#     def get_recipes_count(self, obj):
#         return Recipe.objects.filter(author=obj).count()


class SubscriptionsListSerializer(UserSerializer):
    """Сериализатор для получения подписок"""

    recipes_count = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("recipes_count", "recipes")
        read_only_fields = ("email", "username", "first_name", "last_name")

    # def validate(self, data):
    #     author_id = (
    #         self.context.get("request").parser_context.get("kwargs").get("id")
    #     )
    #     author = get_object_or_404(User, id=author_id)
    #     user = self.context.get("request").user
    #     if user.follower.filter(author=author_id).exists():
    #         raise ValidationError(
    #             detail="Подписка уже существует",
    #             code=HTTP_400_BAD_REQUEST,
    #         )
    #     if user == author:
    #         raise ValidationError(
    #             detail="Нельзя подписаться на самого себя",
    #             code=status.HTTP_400_BAD_REQUEST,
    #         )
    #     return data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get("request")
        limit = request.GET.get("recipes_limit")
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[: int(limit)]
        serializer = RecipeShortSerializer(recipes, many=True, read_only=True)
        return serializer.data


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор подписок."""

    class Meta:
        model = Subscriptions
        fields = ["user", "author"]
        validators = [
            UniqueTogetherValidator(
                queryset=Subscriptions.objects.all(),
                fields=["user", "author"],
            )
        ]

    def to_representation(self, instance):
        return SubscriptionsListSerializer(
            instance.author, context={"request": self.context.get("request")}
        ).data


class FavoriteListSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения избранного."""

    class Meta:
        model = Recipe
        fields = ["id", "name", "image", "cooking_time"]


class RecipeCartSerializer(serializers.ModelSerializer):
    """Сериализатор для списка покупок."""

    class Meta:
        model = RecipeCart
        fields = ["user", "recipe"]

    def to_representation(self, instance):
        return FavoriteListSerializer(
            instance.recipe, context={"request": self.context.get("request")}
        ).data


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор модели Избранное."""

    class Meta:
        model = Favorite
        fields = ["user", "recipe"]

    def to_representation(self, instance):
        return FavoriteListSerializer(
            instance.recipe, context={"request": self.context.get("request")}
        ).data
