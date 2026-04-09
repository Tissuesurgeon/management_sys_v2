from django.contrib import admin

from workforce.models import CalendarEvent, Profile, TaskState, Worker, WorkerInvitation


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'photo')
    list_filter = ('role',)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_id', 'department', 'user')
    search_fields = ('name', 'employee_id')


@admin.register(WorkerInvitation)
class WorkerInvitationAdmin(admin.ModelAdmin):
    list_display = ('invite_code', 'name', 'email', 'employee_id', 'claimed_at', 'created_at')
    list_filter = ('claimed_at',)
    search_fields = ('invite_code', 'name', 'email', 'employee_id')
    readonly_fields = ('invite_code', 'claimed_at', 'claimed_by', 'created_at', 'created_by')


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start', 'assigned_worker', 'recurrence_type')
    list_filter = ('recurrence_type', 'color')
    search_fields = ('title', 'location')


@admin.register(TaskState)
class TaskStateAdmin(admin.ModelAdmin):
    list_display = ('derived_task_id', 'status', 'last_saved_at')
    search_fields = ('derived_task_id',)
