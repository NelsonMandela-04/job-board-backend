from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from rest_framework import serializers

from .models import (
    Company,
    Job,
    Resume,
    Application,
    Interview,
    SavedJob,
    Notification,
    UserProfile,
    Conversation,
    Message,
    AdminActivityLog,
)


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
        ]


class ProfileSerializer(serializers.ModelSerializer):

    is_employer = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    profile_photo_updated_at = serializers.DateTimeField(
        read_only=True
    )
    next_photo_change = serializers.SerializerMethodField()
    profile_photo_locked = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "first_name",
            "email",
            "is_staff",
            "is_active",
            "is_employer",
            "profile_photo",
            "profile_photo_updated_at",
            "next_photo_change",
            "profile_photo_locked",
            "resume",
        ]

    def get_is_employer(self, obj):
        return (
            not obj.is_staff
            and obj.companies.exists()
        )

    def get_profile_photo(self, obj):
        try:
            profile = obj.profile
        except UserProfile.DoesNotExist:
            return None

        if not profile.profile_photo:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(
                profile.profile_photo.url
            )

        return profile.profile_photo.url

    def get_next_photo_change(self, obj):
        try:
            profile = obj.profile
        except UserProfile.DoesNotExist:
            return None

        if not profile.profile_photo_updated_at:
            return None

        return (
            profile.profile_photo_updated_at
            + timedelta(days=24)
        )

    def get_profile_photo_locked(self, obj):
        try:
            profile = obj.profile
        except UserProfile.DoesNotExist:
            return False

        if not profile.profile_photo_updated_at:
            return False

        return (
            timezone.now()
            <
            profile.profile_photo_updated_at
            + timedelta(days=24)
        )

    def get_resume(self, obj):
        try:
            resume = obj.resume
        except Resume.DoesNotExist:
            return None

        request = self.context.get("request")

        file_url = resume.file.url

        if request:
            file_url = request.build_absolute_uri(
                file_url
            )

        return {
            "id": resume.id,
            "file": file_url,
            "name": resume.file.name.split("/")[-1],
            "uploaded_at": resume.uploaded_at,
        }


class PublicProfileSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    first_name = serializers.CharField(
        source="user.first_name",
        read_only=True
    )

    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile

        fields = [
            "username",
            "first_name",
            "profile_photo",
            "bio",
            "location",
            "skills",
            "education",
            "experience",
        ]

        read_only_fields = [
            "username",
            "first_name",
            "profile_photo",
        ]

    def get_profile_photo(self, obj):
        if not obj.profile_photo:
            return None

        request = self.context.get("request")

        url = obj.profile_photo.url

        if request:
            return request.build_absolute_uri(url)

        return url


class CompanySerializer(serializers.ModelSerializer):

    owner = serializers.ReadOnlyField(
        source="owner.username"
    )

    class Meta:
        model = Company

        fields = [
            "id",
            "name",
            "description",
            "website",
            "location",
            "logo",
            "owner",
            "is_active",
            "is_suspended",
            "suspension_reason",
            "suspended_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "owner",
            "is_active",
            "is_suspended",
            "suspension_reason",
            "suspended_at",
            "created_at",
        ]


class JobSerializer(serializers.ModelSerializer):

    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all()
    )

    company_details = CompanySerializer(
        source="company",
        read_only=True
    )

    class Meta:
        model = Job

        fields = [
            "id",
            "company",
            "company_details",
            "title",
            "description",
            "location",
            "latitude",
            "longitude",
            "job_type",
            "salary",
            "requirements",
            "is_approved",
            "moderation_status",
            "rejection_reason",
            "status",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "company_details",
            "is_approved",
            "moderation_status",
            "rejection_reason",
            "status",
            "created_at",
        ]


class ResumeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Resume

        fields = [
            "id",
            "user",
            "file",
            "uploaded_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "uploaded_at",
        ]


class ApplicationSerializer(serializers.ModelSerializer):

    applicant = UserSerializer(
        read_only=True
    )

    job_details = JobSerializer(
        source="job",
        read_only=True
    )

    class Meta:
        model = Application

        fields = [
            "id",
            "job",
            "job_details",
            "applicant",
            "resume",
            "cover_letter",
            "status",
            "applied_at",
        ]

        read_only_fields = [
            "id",
            "applicant",
            "status",
            "applied_at",
            "resume",
        ]


class InterviewSerializer(serializers.ModelSerializer):

    applicant_name = serializers.SerializerMethodField()

    applicant_username = serializers.CharField(
        source="application.applicant.username",
        read_only=True
    )

    job_title = serializers.CharField(
        source="application.job.title",
        read_only=True
    )

    company_name = serializers.CharField(
        source="application.job.company.name",
        read_only=True
    )

    class Meta:
        model = Interview

        fields = [
            "id",
            "application",
            "applicant_name",
            "applicant_username",
            "job_title",
            "company_name",
            "scheduled_by",
            "interview_type",
            "scheduled_at",
            "meeting_link",
            "location",
            "message",
            "status",
            "attendance_status",
            "reschedule_requested",
            "preferred_date",
            "preferred_time",
            "reschedule_reason",
            "candidate_response_at",
            "candidate_response_message",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "applicant_name",
            "applicant_username",
            "job_title",
            "company_name",
            "scheduled_by",
            "status",
            "attendance_status",
            "reschedule_requested",
            "preferred_date",
            "preferred_time",
            "reschedule_reason",
            "candidate_response_at",
            "candidate_response_message",
            "created_at",
            "updated_at",
        ]

    def get_applicant_name(self, obj):
        return (
            obj.application.applicant.get_full_name()
            or obj.application.applicant.username
        )

    def validate(self, attrs):
        interview_type = attrs.get(
            "interview_type",
            getattr(
                self.instance,
                "interview_type",
                None
            )
        )

        meeting_link = attrs.get(
            "meeting_link",
            getattr(
                self.instance,
                "meeting_link",
                ""
            )
        )

        location = attrs.get(
            "location",
            getattr(
                self.instance,
                "location",
                ""
            )
        )

        scheduled_at = attrs.get(
            "scheduled_at",
            getattr(
                self.instance,
                "scheduled_at",
                None
            )
        )

        if scheduled_at:
            if scheduled_at <= timezone.now():
                raise serializers.ValidationError({
                    "scheduled_at": (
                        "Interview date and time "
                        "must be in the future."
                    )
                })

        if interview_type == "online" and not meeting_link:
            raise serializers.ValidationError({
                "meeting_link": (
                    "A meeting link is required "
                    "for online interviews."
                )
            })

        if interview_type == "in_person" and not location:
            raise serializers.ValidationError({
                "location": (
                    "A physical location is required "
                    "for in-person interviews."
                )
            })

        return attrs


class SavedJobSerializer(serializers.ModelSerializer):

    job_details = JobSerializer(
        source="job",
        read_only=True
    )

    class Meta:
        model = SavedJob

        fields = [
            "id",
            "job",
            "job_details",
            "saved_at",
        ]

        read_only_fields = [
            "id",
            "saved_at",
            "job_details",
        ]



class NotificationSerializer(serializers.ModelSerializer):

    job_title = serializers.CharField(
        source="job.title",
        read_only=True
    )

    class Meta:
        model = Notification

        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "job",
            "job_title",
            "application",
            "is_read",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "job",
            "job_title",
            "application",
            "created_at",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSerializer(
        many=True,
        read_only=True
    )

    latest_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "participants",
            "subject",
            "status",
            "created_at",
            "updated_at",
            "latest_message",
        ]

        read_only_fields = [
            "id",
            "participants",
            "created_at",
            "updated_at",
            "latest_message",
        ]

    def get_latest_message(self, obj):
        message = obj.messages.order_by(
            "-created_at"
        ).first()

        if not message:
            return None

        return MessageSerializer(
            message,
            context=self.context
        ).data


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username",
        read_only=True
    )

    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "sender_username",
            "sender_name",
            "message",
            "is_read",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "sender",
            "sender_username",
            "sender_name",
            "is_read",
            "created_at",
        ]

    def get_sender_name(self, obj):
        full_name = obj.sender.get_full_name().strip()

        if full_name:
            return full_name

        return obj.sender.username
    

class AdminActivityLogSerializer(serializers.ModelSerializer):

    admin_username = serializers.CharField(
        source="admin.username",
        read_only=True
    )

    target_username = serializers.CharField(
        source="target_user.username",
        read_only=True
    )

    target_company_name = serializers.CharField(
        source="target_company.name",
        read_only=True
    )

    target_job_title = serializers.CharField(
        source="target_job.title",
        read_only=True
    )

    action_display = serializers.CharField(
        source="get_action_display",
        read_only=True
    )

    class Meta:
        model = AdminActivityLog

        fields = [
            "id",
            "admin",
            "admin_username",
            "action",
            "action_display",
            "target_user",
            "target_username",
            "target_company",
            "target_company_name",
            "target_job",
            "target_job_title",
            "reason",
            "details",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "admin",
            "admin_username",
            "action",
            "action_display",
            "target_user",
            "target_username",
            "target_company",
            "target_company_name",
            "target_job",
            "target_job_title",
            "reason",
            "details",
            "created_at",
        ]