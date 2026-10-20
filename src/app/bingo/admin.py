from django.contrib import admin

from .models import Player, Room


class PlayerInline(admin.TabularInline):
    model = Player
    fields = ('nickname', 'removed', 'joined_at')
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'stage', 'player_count', 'last_activity_at', 'created_at')
    readonly_fields = ('code', 'created_at', 'last_activity_at', 'auto_interval')
    inlines = [PlayerInline]

    @admin.display(description='stage')
    def stage(self, room):
        return room.game.get_stage_display() if hasattr(room, 'game') else '-'

    @admin.display(description='players')
    def player_count(self, room):
        return room.players.filter(removed=False).count()
