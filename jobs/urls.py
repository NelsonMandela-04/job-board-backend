from django.urls import path, include

from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    JobViewSet,
    ResumeViewSet,
    ApplicationViewSet,
    InterviewViewSet,
    SavedJobViewSet,
    NotificationViewSet,
    ConversationViewSet,
    ProfileView,
    PublicProfileView,
    register_user,
    login_user,
    bootstrap_admin,
    AdminDashboardView,
    AdminUsersView,
    AdminCompaniesView,
    AdminApplicationsView,
    password_reset_request,
    password_reset_confirm,
)

router = DefaultRouter()

router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"resumes", ResumeViewSet, basename="resume")
router.register(r"applications", ApplicationViewSet, basename="application")
router.register(r"saved-jobs", SavedJobViewSet, basename="saved-job")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"conversations", ConversationViewSet, basename="conversation")
router.register(r"interviews", InterviewViewSet, basename="interview")

urlpatterns = [
    path("", include(router.urls)),
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("bootstrap-admin/", bootstrap_admin, name="bootstrap-admin"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password-reset/", password_reset_request, name="password-reset"),
    path("password-reset-confirm/", password_reset_confirm, name="password-reset-confirm"),
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/users/", AdminUsersView.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", AdminUsersView.as_view(), name="admin-user-detail"),
    path("admin/companies/", AdminCompaniesView.as_view(), name="admin-companies"),
    path("admin/companies/<int:company_id>/", AdminCompaniesView.as_view(), name="admin-company-detail"),
    path("admin/applications/", AdminApplicationsView.as_view(), name="admin-applications"),
    path("public-profile/<str:username>/", PublicProfileView.as_view(), name="public-profile"),
]