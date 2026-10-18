from django.contrib import admin
from .models import KidProfile


@admin.register(KidProfile)
class KidProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'state', 'failed_attempts', 'locked_until', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['pin_hash', 'setup_code_hash', 'setup_code_expires_at', 'created_at']
