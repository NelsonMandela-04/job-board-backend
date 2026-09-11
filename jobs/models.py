from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="companies"
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    logo = models.ImageField(
        upload_to="company_logos/",
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    is_suspended = models.BooleanField(
        default=False
    )

    suspension_reason = models.TextField(
        blank=True,
        null=True
    )

    suspended_at = models.DateTimeField(
        blank=True,
        null=True
    )

    suspended_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies_suspended"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


class Job(models.Model):
    JOB_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
    ]

    MODERATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    JOB_STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jobs"
    )

    title = models.CharField(
        max_length=200
    )

    description = models.TextField()

    location = models.CharField(
        max_length=200
    )

    latitude = models.FloatField(
        null=True,
        blank=True
    )

    longitude = models.FloatField(
        null=True,
        blank=True
    )

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES,
        default="full_time"
    )

    salary = models.CharField(
        max_length=100,
        blank=True
    )

    requirements = models.TextField(
        blank=True
    )

    is_approved = models.BooleanField(
        default=False
    )

    moderation_status = models.CharField(
        max_length=20,
        choices=MODERATION_STATUS_CHOICES,
        default="pending"
    )

    rejection_reason = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=10,
        choices=JOB_STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title


class Resume(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="resume"
    )

    file = models.FileField(
        upload_to="resumes/"
    )

    uploaded_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.user.username}'s Resume"


class Application(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("under_review", "Under Review"),
        ("shortlisted", "Shortlisted"),
        ("interview", "Interview"),
        ("offer", "Offer"),
        ("hired", "Hired"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
        ("reviewed", "Reviewed"),
        ("accepted", "Accepted"),
    ]

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications"
    )

    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="applications"
    )

    resume = models.ForeignKey(
        Resume,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    cover_letter = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    applied_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            "job",
            "applicant"
        )

    def __str__(self):
        return (
            f"{self.applicant.username} - "
            f"{self.job.title}"
        )


class Interview(models.Model):
    INTERVIEW_TYPE_CHOICES = [
        ("online", "Online"),
        ("in_person", "In Person"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
        ("declined", "Declined"),
    ]

    ATTENDANCE_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
    ]

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="interviews"
    )

    scheduled_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="scheduled_interviews"
    )

    interview_type = models.CharField(
        max_length=20,
        choices=INTERVIEW_TYPE_CHOICES
    )

    scheduled_at = models.DateTimeField()

    meeting_link = models.URLField(
        blank=True
    )

    location = models.CharField(
        max_length=300,
        blank=True
    )

    message = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled"
    )

    attendance_status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_CHOICES,
        default="pending"
    )

    reschedule_requested = models.BooleanField(
        default=False
    )

    preferred_date = models.DateField(
        null=True,
        blank=True
    )

    preferred_time = models.TimeField(
        null=True,
        blank=True
    )

    reschedule_reason = models.TextField(
        blank=True
    )

    candidate_response_at = models.DateTimeField(
        null=True,
        blank=True
    )

    candidate_response_message = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.application.applicant.username} - "
            f"{self.application.job.title} - "
            f"{self.scheduled_at}"
        )


class SavedJob(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_jobs"
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="saved_by"
    )

    saved_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            "user",
            "job"
        )

    def __str__(self):
        return (
            f"{self.user.username} "
            f"saved {self.job.title}"
        )


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        (
            "application_submitted",
            "Application Submitted"
        ),
        (
            "application_reviewed",
            "Application Reviewed"
        ),
        (
            "application_shortlisted",
            "Application Shortlisted"
        ),
        (
            "application_interview",
            "Application Interview"
        ),
        (
            "application_offer",
            "Job Offer"
        ),
        (
            "application_hired",
            "Application Hired"
        ),
        (
            "application_rejected",
            "Application Rejected"
        ),
        (
            "application_withdrawn",
            "Application Withdrawn"
        ),
        (
            "application_accepted",
            "Application Accepted"
        ),
        (
            "job_posted",
            "Job Posted"
        ),
        (
            "job_approved",
            "Job Approved"
        ),
        (
            "job_rejected",
            "Job Rejected"
        ),
        (
            "interview_scheduled",
            "Interview Scheduled"
        ),
        (
            "interview_rescheduled",
            "Interview Rescheduled"
        ),
        (
            "interview_cancelled",
            "Interview Cancelled"
        ),
        (
            "interview_completed",
            "Interview Completed"
        ),
        (
            "interview_attendance_confirmed",
            "Interview Attendance Confirmed"
        ),
        (
            "interview_declined",
            "Interview Declined"
        ),
        (
            "interview_reschedule_requested",
            "Interview Reschedule Requested"
        ),
        (
            "interview_reschedule_approved",
            "Interview Reschedule Approved"
        ),
        (
            "interview_reschedule_rejected",
            "Interview Reschedule Rejected"
        ),
        (
            "employer_suspended",
            "Employer Suspended"
        ),
        (
            "employer_reactivated",
            "Employer Reactivated"
        ),
        (
            "company_suspended",
            "Company Suspended"
        ),
        (
            "company_reactivated",
            "Company Reactivated"
        ),
        (
            "account_deactivated",
            "Account Deactivated"
        ),
        (
            "account_reactivated",
            "Account Reactivated"
        ),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True
    )

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True
    )

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.title}"
        )


class UserProfile(models.Model):
    PRIVACY_CHOICES = [
        ("public", "Public"),
        ("employers", "Employers Only"),
        ("private", "Private"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    profile_photo = models.ImageField(
        upload_to="profile_photos/",
        blank=True,
        null=True
    )

    profile_photo_updated_at = models.DateTimeField(
        blank=True,
        null=True
    )

    bio = models.TextField(
        blank=True,
        max_length=1000
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    skills = models.TextField(
        blank=True,
        help_text="Enter skills separated by commas."
    )

    education = models.TextField(
        blank=True,
        max_length=2000
    )

    experience = models.TextField(
        blank=True,
        max_length=3000
    )

    privacy = models.CharField(
        max_length=20,
        choices=PRIVACY_CHOICES,
        default="public"
    )

    account_deactivation_reason = models.TextField(
        blank=True,
        null=True
    )

    account_deactivated_at = models.DateTimeField(
        blank=True,
        null=True
    )

    account_deactivated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts_deactivated"
    )

    def __str__(self):
        return f"{self.user.username} Profile"


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    participants = models.ManyToManyField(
        User,
        related_name="conversations"
    )

    subject = models.CharField(
        max_length=200
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        participant_names = ", ".join(
            self.participants.values_list(
                "username",
                flat=True
            )
        )

        return (
            f"{self.subject} - "
            f"{participant_names}"
        )

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.sender.username} - "
            f"{self.conversation.subject}"
        )


class AdminActivityLog(models.Model):
    ACTION_CHOICES = [
        ("user_deactivated", "User Deactivated"),
        ("user_reactivated", "User Reactivated"),
        ("user_deleted", "User Deleted"),
        ("employer_suspended", "Employer Suspended"),
        ("employer_reactivated", "Employer Reactivated"),
        ("company_suspended", "Company Suspended"),
        ("company_reactivated", "Company Reactivated"),
        ("company_deactivated", "Company Deactivated"),
        ("company_reactivated", "Company Reactivated"),
        ("company_deleted", "Company Deleted"),
        ("job_approved", "Job Approved"),
        ("job_rejected", "Job Rejected"),
        ("job_deleted", "Job Deleted"),
        ("application_updated", "Application Updated"),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_activity_logs"
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES
    )

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_actions_received"
    )

    target_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_activity_logs"
    )

    target_job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_activity_logs"
    )

    reason = models.TextField(
        blank=True
    )

    details = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-created_at"
        ]

    def __str__(self):
        admin_name = (
            self.admin.username
            if self.admin
            else "System"
        )

        return (
            f"{admin_name} - "
            f"{self.action} - "
            f"{self.created_at}"
        )