from djoser.views import UserViewSet
from rest_framework.pagination import PageNumberPagination

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http.response import HttpResponse
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)
from django.db.models import Sum

from django.shortcuts import get_object_or_404


from api.permissions import IsOwnerOrReadOnly, AdminOrReadOnly
from api.serializers import (
    UserSerializer,
    RecipeListSerializer,
    RecipeCreateUpdateSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeShortSerializer,
    SubscribeSerializer,
)
from recipes.models import (
    Recipe,
    Tag,
    Ingredient,
    RecipeIngredient,
    RecipeCart,
    Favorite,
)
from users.models import Subscriptions

User = get_user_model()


class CustomPagination(PageNumberPagination):
    """Кастомный паджинатор. Ожидается параметр limit."""

    page_size_query_param = "limit"


class CustomUserViewSet(UserViewSet):
    """Api для работы с пользователями."""

    serializer_class = UserSerializer
    queryset = User.objects.all()
    pagination_class = CustomPagination
    page_size = 6

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(subscribers__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscribeSerializer(
            pages, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, **kwargs):
        user = request.user
        author_id = self.kwargs.get("id")
        author = get_object_or_404(User, id=author_id)

        if request.method == "POST":
            serializer = SubscribeSerializer(
                author, data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            Subscriptions.objects.create(user=user, author=author)
            return Response(serializer.data, status=HTTP_201_CREATED)

        if request.method == "DELETE":
            subscription = get_object_or_404(
                Subscriptions, user=user, author=author
            )
            subscription.delete()
            return Response(status=HTTP_204_NO_CONTENT)


class RecipesViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    http_method_names = [
        "get",
        "post",
        "patch",
        "delete",
    ]
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)
    pagination_class = CustomPagination
    page_size = 6

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RecipeCreateUpdateSerializer

        return RecipeListSerializer

    def get_queryset(self):
        qs = Recipe.objects.add_user_annotations(self.request.user.pk)

        # Фильтры из GET-параметров запроса, например.
        author = self.request.query_params.get("author", None)
        if author:
            qs = qs.filter(author=author)

        tags = self.request.query_params.getlist("tags")
        if tags:
            qs = qs.filter(tags=tags)  # .distinct()

        return qs

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        if not user.carts.exists():
            return Response(status=HTTP_400_BAD_REQUEST)

        ingredients = (
            RecipeIngredient.objects.filter(recipe__in_carts__user=user)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(amount=Sum("amount"))
        )

        shopping_list = "Список покупок: \n\n"
        shopping_list += "\n".join(
            [
                f'- {ingredient["ingredient__name"]} '
                f'({ingredient["ingredient__measurement_unit"]})'
                f' - {ingredient["amount"]}'
                for ingredient in ingredients
            ]
        )
        shopping_list += "\n\nFoodgram."

        filename = "shopping_list.txt"
        response = HttpResponse(shopping_list, content_type="text/plain")
        response["Content-Disposition"] = f"attachment; filename={filename}"

        return response

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk):
        if request.method == "POST":
            return self.add_to(RecipeCart, request.user, pk)
        else:
            return self.delete_from(RecipeCart, request.user, pk)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk):
        if request.method == "POST":
            return self.add_to(Favorite, request.user, pk)
        else:
            return self.delete_from(Favorite, request.user, pk)

    def add_to(self, model, user, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response(
                {"errors": "Рецепт уже добавлен!"},
                status=HTTP_400_BAD_REQUEST,
            )
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = RecipeShortSerializer(recipe)
        return Response(serializer.data, status=HTTP_201_CREATED)

    def delete_from(self, model, user, pk):
        obj = model.objects.filter(user=user, recipe__id=pk)
        if obj.exists():
            obj.delete()
            return Response(status=HTTP_204_NO_CONTENT)
        return Response(
            {"errors": "Рецепт уже удален!"},
            status=HTTP_400_BAD_REQUEST,
        )


class TagViewSet(ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    pagination_class = None
    permission_classes = (AdminOrReadOnly,)


class IngredientViewSet(ModelViewSet):
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
