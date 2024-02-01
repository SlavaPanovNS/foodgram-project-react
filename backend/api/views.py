from djoser.views import UserViewSet
from rest_framework.pagination import PageNumberPagination

# from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.contrib.auth import get_user_model


# from api.permissions import IsOwnerOrReadOnly
from api.serializers import (
    UserSerializer,
    RecipeListSerializer,
    RecipeCreateUpdateSerializer,
    TagSerializer,
    IngredientSerializer,
)
from recipes.models import Recipe, Tag, Ingredient

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


class RecipesViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    http_method_names = [
        "get",
        "post",
        "patch",
    ]
    # permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)
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


class TagViewSet(ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    pagination_class = None


class IngredientViewSet(ModelViewSet):
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
