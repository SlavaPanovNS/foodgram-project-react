from django.contrib import admin

from recipes.models import (
    Recipe,
    Ingredient,
    RecipeIngredient,
    Favorite,
    Tag,
    RecipeCart,
)

admin.site.site_header = "Администрирование Foodgram"

admin.site.register(Recipe)
admin.site.register(Ingredient)
admin.site.register(RecipeIngredient)
admin.site.register(Favorite)
admin.site.register(Tag)
admin.site.register(RecipeCart)
