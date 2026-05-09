from django.contrib import admin
from .models import Chore, FercoinTransaction


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'fercoins', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(FercoinTransaction)
class FercoinTransactionAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'amount', 'chore', 'note', 'given_by', 'created_at']
    list_filter = ['recipient', 'given_by']
    search_fields = ['note', 'recipient__username']
    readonly_fields = ['created_at']
