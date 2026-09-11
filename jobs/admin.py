
from django.contrib import admin
from .models import Company, Job, Resume, Application, SavedJob


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "location",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "owner__username",
    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "company",
        "location",
        "is_approved",
        "created_at",
    )

    list_filter = (
        "is_approved",
        "job_type",
        "created_at",
    )

    search_fields = (
        "title",
        "company__name",
        "location",
    )

    list_editable = (
        "is_approved",
    )


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "uploaded_at",
    )

    search_fields = (
        "user__username",
        "user__email",
    )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "applicant",
        "status",
        "applied_at",
    )

    list_filter = (
        "status",
        "applied_at",
    )

    search_fields = (
        "job__title",
        "applicant__username",
        "applicant__email",
    )


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "job",
        "saved_at",
    )

    search_fields = (
        "user__username",
        "job__title",
    )
