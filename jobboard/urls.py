
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from jobs.views import AdminCompaniesView
from jobs.views import AdminApplicationsView

from jobs.views import (
    ProfileView,
    AdminUsersView,
    AdminCompaniesView,
    AdminDashboardView,
    AdminApplicationsView,
)

urlpatterns = [
    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "api/",
        include("jobs.urls")
    ),

    path(
        "api/profile/",
        ProfileView.as_view(),
        name="profile"
    ),

    path(
        "api/admin/dashboard/",
        AdminDashboardView.as_view(),
        name="admin-dashboard"
    ),

    path(
        "api/admin/users/",
        AdminUsersView.as_view(),
        name="admin-users"
    ),

    path(
        "api/admin/users/<int:user_id>/",
        AdminUsersView.as_view(),
        name="admin-user-detail"
    ),

    path(
        "api/admin/companies/",
        AdminCompaniesView.as_view(),
        name="admin-companies"
    ),

    path(
        "api/admin/companies/<int:company_id>/",
        AdminCompaniesView.as_view(),
        name="admin-company-detail"
    ),

    path(
        "api/admin/applications/",
        AdminApplicationsView.as_view(),
        name="admin-applications"
    ),

    path(
    "api/admin/companies/",
    AdminCompaniesView.as_view(),
    name="admin-companies"
    ),

    path(
    "api/admin/applications/",
    AdminApplicationsView.as_view(),
    name="admin-applications"
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
