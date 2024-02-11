from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from djoser.views import UserViewSet

from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeCart,
    RecipeIngredient,
    Tag,
)
from users.models import Subscriptions

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthorOrAdminOrReadOnly
from api.serializers import (
    FavoriteSerializer,
    IngredientSerializer,
    RecipeCartSerializer,
    RecipeCreateUpdateSerializer,
    RecipeListSerializer,
    RecipeShortSerializer,
    SubscriptionSerializer,
    SubscriptionsListSerializer,
    TagSerializer,
    UserSerializer,
)

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
        serializer = SubscriptionsListSerializer(
            pages, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, pk=id)
        if request.method == "POST":
            serializer = SubscriptionsListSerializer(
                author,
                data=request.data,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            Subscriptions.objects.create(user=user, author=author)
            return Response(serializer.data, status=HTTP_201_CREATED)

        if request.method == "DELETE":
            subscription = get_object_or_404(
                Subscriptions,
                author=author,
                user=user,
            )
            subscription.delete()
            return Response(status=HTTP_204_NO_CONTENT)


class SubscribeView(APIView):
    """Операция подписки/отписки."""

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, id):
        data = {"user": request.user.id, "author": id}
        serializer = SubscriptionSerializer(
            data=data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=HTTP_201_CREATED)
        return Response(status=HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        author = get_object_or_404(User, id=id)
        if Subscriptions.objects.filter(
            user=request.user, author=author
        ).exists():
            subscription = get_object_or_404(
                Subscriptions, user=request.user, author=author
            )
            subscription.delete()
            return Response(status=HTTP_204_NO_CONTENT)
        return Response(status=HTTP_400_BAD_REQUEST)


class ShowSubscriptionsView(ListAPIView):
    """Отображение подписок."""

    permission_classes = [
        IsAuthenticated,
    ]
    pagination_class = CustomPagination

    def get(self, request):
        user = request.user
        queryset = User.objects.filter(author__user=user)
        page = self.paginate_queryset(queryset)
        serializer = SubscriptionsListSerializer(
            page, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)


class RecipesViewSet(ModelViewSet):
    """API для работы с рецептами."""

    permission_classes = [
        IsAuthorOrAdminOrReadOnly,
    ]
    pagination_class = CustomPagination
    queryset = Recipe.objects.all()
    filter_backends = [
        DjangoFilterBackend,
    ]
    filterset_class = RecipeFilter

    def get_queryset(self):
        queryset = self.queryset

        tags = self.request.query_params.getlist("tags")
        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()

        author = self.request.query_params.get("author")
        if author:
            queryset = queryset.filter(author=author)

        return queryset

    def get_serializer_class(self):
        if self.request.method == "GET":
            return RecipeListSerializer
        return RecipeCreateUpdateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        if not user.shopping_cart.exists():
            return Response(status=HTTP_400_BAD_REQUEST)

        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
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


class FavoriteView(APIView):
    """Добавление/удаление рецепта из избранного."""

    permission_classes = [
        IsAuthenticated,
    ]
    pagination_class = CustomPagination

    def post(self, request, id):
        data = {"user": request.user.id, "recipe": id}
        if not Favorite.objects.filter(
            user=request.user, recipe__id=id
        ).exists():
            serializer = FavoriteSerializer(
                data=data, context={"request": request}
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=HTTP_201_CREATED)
        return Response(status=HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        recipe = get_object_or_404(Recipe, id=id)
        if Favorite.objects.filter(user=request.user, recipe=recipe).exists():
            Favorite.objects.filter(user=request.user, recipe=recipe).delete()
            return Response(status=HTTP_204_NO_CONTENT)
        return Response(status=HTTP_400_BAD_REQUEST)


class TagViewSet(ReadOnlyModelViewSet):
    """API для работы с тэгами."""

    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    pagination_class = None
    permission_classes = [
        AllowAny,
    ]


class IngredientViewSet(ReadOnlyModelViewSet):
    """API для работы с ингредиентами."""

    permission_classes = [
        AllowAny,
    ]
    pagination_class = None
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter
    filterset_fields = ["name"]


class ShoppingCartView(APIView):
    """Добавление рецепта в корзину или его удаление."""

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, id):
        data = {"user": request.user.id, "recipe": id}
        recipe = get_object_or_404(Recipe, id=id)
        if not RecipeCart.objects.filter(
            user=request.user, recipe=recipe
        ).exists():
            serializer = RecipeCartSerializer(
                data=data, context={"request": request}
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=HTTP_201_CREATED)
        return Response(status=HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        recipe = get_object_or_404(Recipe, id=id)
        if RecipeCart.objects.filter(
            user=request.user, recipe=recipe
        ).exists():
            RecipeCart.objects.filter(
                user=request.user, recipe=recipe
            ).delete()
            return Response(status=HTTP_204_NO_CONTENT)
        return Response(status=HTTP_400_BAD_REQUEST)
