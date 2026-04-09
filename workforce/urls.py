from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'workforce'

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('admin/calendar/new/', views.admin_calendar_create, name='admin_calendar_create'),
    path('admin/calendar/<int:pk>/edit/', views.admin_calendar_edit, name='admin_calendar_edit'),
    path('admin/calendar/<int:pk>/delete/', views.admin_calendar_delete, name='admin_calendar_delete'),
    path('admin/calendar/', views.admin_calendar_list, name='admin_calendar_list'),
    path('admin/tasks/', views.admin_tasks, name='admin_tasks'),
    path('admin/reports/tasks/', views.admin_task_report, name='admin_task_report'),
    path('admin/workers/invites/new/', views.admin_worker_invite_create, name='admin_worker_invite_create'),
    path('admin/workers/invites/', views.admin_worker_invites, name='admin_worker_invites'),
    path('admin/workers/<int:pk>/', views.admin_worker_detail, name='admin_worker_detail'),
    path('admin/workers/', views.admin_workers, name='admin_workers'),
    path('admin/import/', views.admin_import, name='admin_import'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/profile/', views.admin_profile, name='admin_profile'),
    path(
        'admin/',
        RedirectView.as_view(pattern_name='workforce:admin_dashboard', permanent=False),
    ),
    path('worker/task/<int:event_id>/<str:date_key>/', views.worker_task_detail, name='worker_task_detail'),
    path('worker/schedule/', views.worker_schedule, name='worker_schedule'),
    path('worker/history/', views.worker_history, name='worker_history'),
    path('worker/profile/', views.worker_profile, name='worker_profile'),
    path('worker/tasks/', views.worker_my_tasks, name='worker_my_tasks'),
    path(
        'worker/',
        RedirectView.as_view(pattern_name='workforce:worker_my_tasks', permanent=False),
    ),
]
