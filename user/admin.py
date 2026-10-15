from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

@admin.register(User)
class UserAdmin(UserAdmin):
	ordering = ('email',)
	list_display = ('email', 'name', 'role', 'is_active', 'is_staff')
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal info', {'fields': ('name', 'phone', 'location', 'role')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Important dates', {'fields': ('last_login',)}),
	)
	add_fieldsets = (
		(None, {'classes': ('wide',), 'fields': ('email', 'name', 'password1', 'password2')}),
	)
	search_fields = ('email', 'name')
