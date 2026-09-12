import os

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode,
)

from math import radians, sin, cos, sqrt, atan2

from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

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
)

from .serializers import (
    CompanySerializer,
    JobSerializer,
    ResumeSerializer,
    ApplicationSerializer,
    InterviewSerializer,
    SavedJobSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    NotificationSerializer,
    ConversationSerializer,
    MessageSerializer,
)


def parse_boolean(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value in [0, 1]:
            return bool(value)

    if isinstance(value, str):
        value = value.strip().lower()

        if value in [
            "true",
            "1",
            "yes",
            "on",
            "active",
            "suspended",
        ]:
            return True

        if value in [
            "false",
            "0",
            "no",
            "off",
            "inactive",
            "unsuspended",
        ]:
            return False

    raise ValidationError(
        {
            "detail": "Boolean value must be true or false."
        }
    )


def log_admin_activity(
    admin_user,
    obj,
    action_flag,
    message,
):
    content_type = ContentType.objects.get_for_model(
        obj,
        for_concrete_model=True,
    )

    object_id = getattr(
        obj,
        "pk",
        None,
    )

    object_repr = str(obj)

    LogEntry.objects.log_action(
        user_id=admin_user.pk,
        content_type_id=content_type.pk,
        object_id=str(object_id) if object_id else None,
        object_repr=object_repr,
        action_flag=action_flag,
        change_message=message,
    )


def get_user_data(user):
    profile = getattr(
        user,
        "profile",
        None,
    )

    companies = Company.objects.filter(
        owner=user
    )

    active_companies = companies.filter(
        is_active=True,
        is_suspended=False,
    )

    suspended_companies = companies.filter(
        is_suspended=True,
    )

    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "is_employer": companies.exists(),
        "company_count": companies.count(),
        "has_suspended_company": suspended_companies.exists(),
        "has_active_company": active_companies.exists(),
        "profile_photo": (
            profile.profile_photo.url
            if profile
            and profile.profile_photo
            else None
        ),
    }


def is_suspended_employer(user):
    if (
        not user
        or not user.is_authenticated
        or user.is_staff
    ):
        return False

    return Company.objects.filter(
        owner=user,
        is_suspended=True,
    ).exists()


def ensure_employer_not_suspended(user):
    if (
        not user
        or not user.is_authenticated
    ):
        raise PermissionDenied(
            "Authentication is required."
        )

    if not user.is_active:
        raise PermissionDenied(
            "Your account has been deactivated."
        )

    if user.is_staff:
        return

    if is_suspended_employer(user):
        raise PermissionDenied(
            "Your employer account is suspended. "
            "You cannot perform employer actions until "
            "an administrator reactivates your account."
        )


def ensure_company_owner_active(
    company,
    user,
):
    if (
        not user
        or not user.is_authenticated
    ):
        raise PermissionDenied(
            "Authentication is required."
        )

    if not user.is_active:
        raise PermissionDenied(
            "Your account has been deactivated."
        )

    if user.is_staff:
        return

    if company.owner_id != user.id:
        raise PermissionDenied(
            "You do not have permission to manage this company."
        )

    if company.is_suspended:
        reason = getattr(
            company,
            "suspension_reason",
            "",
        )

        message = (
            "Your employer account is suspended. "
            "You cannot perform this action until "
            "an administrator reactivates your account."
        )

        if reason:
            message += (
                f" Reason: {reason}"
            )

        raise PermissionDenied(message)

    if not company.is_active:
        raise PermissionDenied(
            "This company is inactive. "
            "Please contact an administrator."
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    username = str(
        request.data.get(
            "username",
            "",
        )
    ).strip()

    email = str(
        request.data.get(
            "email",
            "",
        )
    ).strip().lower()

    password = str(
        request.data.get(
            "password",
            "",
        )
    )

    first_name = str(
        request.data.get(
            "first_name",
            "",
        )
    ).strip()

    if not username:
        return Response(
            {
                "detail": "Username is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not email:
        return Response(
            {
                "detail": "Email is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not password:
        return Response(
            {
                "detail": "Password is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return Response(
            {
                "detail": (
                    "Password must be at least 8 characters long."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        username__iexact=username
    ).exists():
        return Response(
            {
                "detail": "Username already exists."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        email__iexact=email
    ).exists():
        return Response(
            {
                "detail": "Email already exists."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
    )

    UserProfile.objects.get_or_create(
        user=user
    )

    token, _ = Token.objects.get_or_create(
        user=user
    )

    return Response(
        {
            "token": token.key,
            "user": get_user_data(user),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_user(request):
    username = str(
        request.data.get(
            "username",
            "",
        )
    ).strip()

    password = str(
        request.data.get(
            "password",
            "",
        )
    )

    if not username or not password:
        return Response(
            {
                "detail": (
                    "Username and password are required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(
        request=request,
        username=username,
        password=password,
    )

    if user is None:
        return Response(
            {
                "detail": (
                    "Invalid username or password."
                )
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {
                "detail": (
                    "Your account has been deactivated."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    UserProfile.objects.get_or_create(
        user=user
    )

    token, _ = Token.objects.get_or_create(
        user=user
    )

    return Response(
        {
            "token": token.key,
            "user": get_user_data(user),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def bootstrap_admin(request):
    if User.objects.filter(
        is_superuser=True
    ).exists():
        return Response(
            {
                "detail": (
                    "Bootstrap is disabled because "
                    "an administrator already exists."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    bootstrap_key = request.headers.get(
        "X-Bootstrap-Key"
    )

    expected_key = os.getenv(
        "BOOTSTRAP_ADMIN_KEY",
        ""
    )

    if (
        not expected_key
        or bootstrap_key != expected_key
    ):
        return Response(
            {
                "detail": "Invalid bootstrap key."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    username = str(
        request.data.get(
            "username",
            "",
        )
    ).strip()

    email = str(
        request.data.get(
            "email",
            "",
        )
    ).strip().lower()

    password = str(
        request.data.get(
            "password",
            "",
        )
    )

    if (
        not username
        or not email
        or not password
    ):
        return Response(
            {
                "detail": (
                    "username, email and password "
                    "are required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return Response(
            {
                "detail": (
                    "Password must be at least "
                    "8 characters long."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        username__iexact=username
    ).exists():
        return Response(
            {
                "detail": "Username already exists."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        email__iexact=email
    ).exists():
        return Response(
            {
                "detail": "Email already exists."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
    )

    UserProfile.objects.get_or_create(
        user=user
    )

    token, _ = Token.objects.get_or_create(
        user=user
    )

    return Response(
        {
            "detail": (
                "Production administrator "
                "created successfully."
            ),
            "username": user.username,
            "token": token.key,
        },
        status=status.HTTP_201_CREATED,
    )


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Company.objects.none()

        if self.request.user.is_staff:
            return Company.objects.all().order_by(
                "-created_at"
            )

        return Company.objects.filter(
            owner=self.request.user
        ).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        user = self.request.user

        ensure_employer_not_suspended(
            user
        )

        serializer.save(
            owner=user
        )

    def perform_update(self, serializer):
        company = self.get_object()

        ensure_company_owner_active(
            company,
            self.request.user,
        )

        serializer.save()

    def perform_destroy(self, instance):
        ensure_company_owner_active(
            instance,
            self.request.user,
        )

        instance.delete()


class ResumeViewSet(viewsets.ModelViewSet):
    serializer_class = ResumeSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        return Resume.objects.filter(
            user=self.request.user
        ).order_by(
            "-id"
        )

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )

    def perform_update(self, serializer):
        resume = self.get_object()

        if resume.user_id != self.request.user.id:
            raise PermissionDenied(
                "You do not have permission to modify this resume."
            )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied(
                "You do not have permission to delete this resume."
            )

        instance.delete()


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]

    def get_queryset(self):
        user = self.request.user

        if (
            user.is_authenticated
            and user.is_staff
        ):
            queryset = Job.objects.all()

        elif (
            user.is_authenticated
            and self.action in [
                "update",
                "partial_update",
                "destroy",
                "close",
                "reopen",
                "my_jobs",
            ]
        ):
            queryset = Job.objects.filter(
                company__owner=user
            )

        else:
            queryset = Job.objects.filter(
                is_approved=True,
                moderation_status="approved",
            )

        search = self.request.query_params.get(
            "search"
        )

        location = self.request.query_params.get(
            "location"
        )

        job_type = self.request.query_params.get(
            "job_type"
        )

        company_id = self.request.query_params.get(
            "company"
        )

        company_name = self.request.query_params.get(
            "company_name"
        )

        job_status = self.request.query_params.get(
            "status"
        )

        posted = self.request.query_params.get(
            "posted"
        )

        sort = self.request.query_params.get(
            "sort"
        )

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(requirements__icontains=search)
                | Q(location__icontains=search)
                | Q(company__name__icontains=search)
            )

        if location:
            queryset = queryset.filter(
                location__icontains=location
            )

        if job_type:
            queryset = queryset.filter(
                job_type__iexact=job_type
            )

        if company_id:
            queryset = queryset.filter(
                company_id=company_id
            )

        if company_name:
            queryset = queryset.filter(
                company__name__icontains=company_name
            )

        if job_status:
            queryset = queryset.filter(
                status__iexact=job_status
            )

        if posted:
            now = timezone.now()

            if posted == "today":
                queryset = queryset.filter(
                    created_at__gte=now - timedelta(days=1)
                )

            elif posted == "3days":
                queryset = queryset.filter(
                    created_at__gte=now - timedelta(days=3)
                )

            elif posted == "7days":
                queryset = queryset.filter(
                    created_at__gte=now - timedelta(days=7)
                )

            elif posted == "30days":
                queryset = queryset.filter(
                    created_at__gte=now - timedelta(days=30)
                )

        if sort == "oldest":
            queryset = queryset.order_by(
                "created_at"
            )
        else:
            queryset = queryset.order_by(
                "-created_at"
            )

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        ensure_employer_not_suspended(
            user
        )

        company = serializer.validated_data.get(
            "company"
        )

        if not company:
            raise ValidationError(
                {
                    "company": "Company is required."
                }
            )

        ensure_company_owner_active(
            company,
            user,
        )

        job = serializer.save(
            is_approved=False,
            moderation_status="pending",
        )

        Notification.objects.create(
            user=user,
            notification_type="job_posted",
            title="Job submitted for review",
            message=(
                f'Your job "{job.title}" has been submitted '
                "and is waiting for administrator approval."
            ),
            job=job,
        )

    def perform_update(self, serializer):
        job = self.get_object()

        if self.request.user.is_staff:
            serializer.save()
            return

        ensure_company_owner_active(
            job.company,
            self.request.user,
        )

        if "company" in serializer.validated_data:
            new_company = serializer.validated_data[
                "company"
            ]

            if new_company.id != job.company_id:
                raise ValidationError(
                    {
                        "company": (
                            "A job cannot be moved to another company."
                        )
                    }
                )

        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.is_staff:
            instance.delete()
            return

        ensure_company_owner_active(
            instance.company,
            self.request.user,
        )

        instance.delete()

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def my_jobs(self, request):
        ensure_employer_not_suspended(
            request.user
        )

        jobs = Job.objects.filter(
            company__owner=request.user
        ).order_by(
            "-created_at"
        )

        page = self.paginate_queryset(jobs)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = self.get_serializer(
            jobs,
            many=True,
        )

        return Response(
            serializer.data
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAdminUser],
    )
    def pending_jobs(self, request):
        jobs = Job.objects.filter(
            moderation_status="pending"
        ).order_by(
            "-created_at"
        )

        serializer = self.get_serializer(
            jobs,
            many=True,
        )

        return Response(
            serializer.data
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
    )
    def approve(self, request, pk=None):
        job = self.get_object()

        job.is_approved = True
        job.moderation_status = "approved"
        job.rejection_reason = ""

        job.save(
            update_fields=[
                "is_approved",
                "moderation_status",
                "rejection_reason",
            ]
        )

        Notification.objects.create(
            user=job.company.owner,
            notification_type="job_approved",
            title="Job approved",
            message=(
                f'Your job "{job.title}" has been approved '
                "and is now visible to candidates."
            ),
            job=job,
        )

        users = User.objects.filter(
            is_active=True
        ).exclude(
            id=job.company.owner_id
        )

        for user in users:
            already_notified = Notification.objects.filter(
                user=user,
                job=job,
                notification_type="job_posted",
            ).exists()

            if not already_notified:
                Notification.objects.create(
                    user=user,
                    notification_type="job_posted",
                    title="New job available",
                    message=(
                        f'A new job "{job.title}" has been posted '
                        f'by {job.company.name}.'
                    ),
                    job=job,
                )

        return Response(
            {
                "detail": (
                    "Job approved successfully."
                ),
                "job": self.get_serializer(
                    job
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
    )
    def reject(self, request, pk=None):
        job = self.get_object()

        reason = str(
            request.data.get(
                "reason",
                "",
            )
        ).strip()

        if not reason:
            raise ValidationError(
                {
                    "reason": (
                        "Rejection reason is required."
                    )
                }
            )

        job.is_approved = False
        job.moderation_status = "rejected"
        job.rejection_reason = reason

        job.save(
            update_fields=[
                "is_approved",
                "moderation_status",
                "rejection_reason",
            ]
        )

        Notification.objects.create(
            user=job.company.owner,
            notification_type="job_rejected",
            title="Job rejected",
            message=(
                f'Your job "{job.title}" was rejected. '
                f"Reason: {reason}"
            ),
            job=job,
        )

        return Response(
            {
                "detail": (
                    "Job rejected successfully."
                ),
                "job": self.get_serializer(
                    job
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def close(self, request, pk=None):
        job = self.get_object()

        if not request.user.is_staff:
            ensure_company_owner_active(
                job.company,
                request.user,
            )

        job.status = "closed"

        job.save(
            update_fields=[
                "status"
            ]
        )

        return Response(
            {
                "detail": (
                    "Job closed successfully."
                ),
                "job": self.get_serializer(
                    job
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def reopen(self, request, pk=None):
        job = self.get_object()

        if not request.user.is_staff:
            ensure_company_owner_active(
                job.company,
                request.user,
            )

        job.status = "open"

        job.save(
            update_fields=[
                "status"
            ]
        )

        return Response(
            {
                "detail": (
                    "Job reopened successfully."
                ),
                "job": self.get_serializer(
                    job
                ).data,
            }
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def nearby(self, request):
        latitude = request.query_params.get(
            "latitude"
        )

        longitude = request.query_params.get(
            "longitude"
        )

        radius = request.query_params.get(
            "radius",
            "20",
        )

        if latitude is None or longitude is None:
            raise ValidationError(
                {
                    "detail": (
                        "latitude and longitude are required."
                    )
                }
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)
            radius = float(radius)

        except (
            TypeError,
            ValueError,
        ):
            raise ValidationError(
                {
                    "detail": (
                        "latitude, longitude and radius "
                        "must be valid numbers."
                    )
                }
            )

        if radius < 0:
            raise ValidationError(
                {
                    "radius": (
                        "Radius cannot be negative."
                    )
                }
            )

        jobs = Job.objects.filter(
            is_approved=True,
            moderation_status="approved",
            status="open",
        ).select_related(
            "company"
        )

        results = []

        earth_radius_km = 6371

        for job in jobs:
            if (
                job.latitude is None
                or job.longitude is None
            ):
                continue

            lat1 = radians(latitude)
            lon1 = radians(longitude)

            lat2 = radians(
                float(job.latitude)
            )

            lon2 = radians(
                float(job.longitude)
            )

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = (
                sin(dlat / 2) ** 2
                + cos(lat1)
                * cos(lat2)
                * sin(dlon / 2) ** 2
            )

            c = 2 * atan2(
                sqrt(a),
                sqrt(1 - a),
            )

            distance = earth_radius_km * c

            if distance <= radius:
                results.append(
                    (
                        distance,
                        job,
                    )
                )

        results.sort(
            key=lambda item: item[0]
        )

        data = []

        for distance, job in results:
            serialized = self.get_serializer(
                job
            ).data

            serialized["distance"] = round(
                distance,
                2,
            )

            data.append(
                serialized
            )

        return Response(data)


APPLICATION_TRANSITIONS = {
    "pending": [
        "under_review",
        "rejected",
    ],
    "under_review": [
        "shortlisted",
        "rejected",
    ],
    "shortlisted": [
        "interview",
        "rejected",
    ],
    "interview": [
        "offer",
        "rejected",
    ],
    "offer": [
        "hired",
        "rejected",
    ],
    "hired": [],
    "rejected": [],
    "withdrawn": [],
    "reviewed": [
        "shortlisted",
        "rejected",
    ],
    "accepted": [
        "hired",
    ],
}


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Application.objects.select_related(
                "job",
                "job__company",
                "applicant",
                "resume",
            ).order_by(
                "-applied_at"
            )

        if self.action == "employer_applications":
            return Application.objects.filter(
                job__company__owner=user
            ).select_related(
                "job",
                "job__company",
                "applicant",
                "resume",
            ).order_by(
                "-applied_at"
            )

        return Application.objects.filter(
            applicant=user
        ).select_related(
            "job",
            "job__company",
            "applicant",
            "resume",
        ).order_by(
            "-applied_at"
        )

    def perform_create(self, serializer):
        user = self.request.user

        if Company.objects.filter(
            owner=user
        ).exists():
            raise PermissionDenied(
                "Employers cannot apply for jobs."
            )

        job = serializer.validated_data.get(
            "job"
        )

        if not job:
            raise ValidationError(
                {
                    "job": "Job is required."
                }
            )

        if not job.is_approved:
            raise ValidationError(
                {
                    "job": (
                        "This job is not approved "
                        "and cannot receive applications."
                    )
                }
            )

        if job.moderation_status != "approved":
            raise ValidationError(
                {
                    "job": (
                        "This job has not been approved "
                        "and cannot receive applications."
                    )
                }
            )

        if job.status != "open":
            raise ValidationError(
                {
                    "job": (
                        "This job is closed "
                        "and cannot receive applications."
                    )
                }
            )

        if job.company.is_suspended:
            raise ValidationError(
                {
                    "job": (
                        "This company's employer account is suspended."
                    )
                }
            )

        if Application.objects.filter(
            job=job,
            applicant=user,
        ).exists():
            raise ValidationError(
                {
                    "detail": (
                        "You have already applied "
                        "for this job."
                    )
                }
            )

        resume = serializer.validated_data.get(
            "resume"
        )

        if not resume:
            raise ValidationError(
                {
                    "resume": (
                        "A resume is required "
                        "to apply for a job."
                    )
                }
            )

        application = serializer.save(
            applicant=user,
            resume=resume,
        )

        Notification.objects.create(
            user=job.company.owner,
            notification_type="application_submitted",
            title="New job application",
            message=(
                f"{user.get_full_name() or user.username} "
                f'applied for your job "{job.title}".'
            ),
            application=application,
            job=job,
        )

    def perform_update(self, serializer):
        application = self.get_object()

        if self.request.user.is_staff:
            serializer.save()
            return

        if application.applicant_id == self.request.user.id:
            allowed_fields = {
                "cover_letter",
            }

            invalid_fields = set(
                serializer.validated_data.keys()
            ) - allowed_fields

            if invalid_fields:
                raise PermissionDenied(
                    "You can only update your cover letter."
                )

            serializer.save()
            return

        ensure_company_owner_active(
            application.job.company,
            self.request.user,
        )

        raise PermissionDenied(
            "Employer application changes must use the application status endpoint."
        )

    def perform_destroy(self, instance):
        if self.request.user.is_staff:
            instance.delete()
            return

        if instance.applicant_id == self.request.user.id:
            instance.delete()
            return

        ensure_company_owner_active(
            instance.job.company,
            self.request.user,
        )

        raise PermissionDenied(
            "Employers cannot delete applications."
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def employer_applications(self, request):
        ensure_employer_not_suspended(
            request.user
        )

        applications = Application.objects.filter(
            job__company__owner=request.user
        ).select_related(
            "job",
            "job__company",
            "applicant",
            "resume",
        ).order_by(
            "-applied_at"
        )

        serializer = self.get_serializer(
            applications,
            many=True,
        )

        return Response(
            serializer.data
        )

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated],
    )
    def update_status(
        self,
        request,
        pk=None,
    ):
        application = self.get_object()

        if not request.user.is_staff:
            ensure_company_owner_active(
                application.job.company,
                request.user,
            )

        new_status = str(
            request.data.get(
                "status",
                "",
            )
        ).strip().lower()

        if not new_status:
            raise ValidationError(
                {
                    "status": "Status is required."
                }
            )

        current_status = application.status

        allowed = APPLICATION_TRANSITIONS.get(
            current_status,
            [],
        )

        if new_status not in allowed:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot change application "
                        f"from '{current_status}' "
                        f"to '{new_status}'."
                    )
                }
            )

        application.status = new_status

        application.save(
            update_fields=[
                "status"
            ]
        )

        notification_map = {
            "under_review": (
                "Application under review",
                "Your application is now under review.",
            ),
            "shortlisted": (
                "Application shortlisted",
                "Your application has been shortlisted.",
            ),
            "interview": (
                "Application moved to interview",
                "Your application has moved to the interview stage.",
            ),
            "offer": (
                "Job offer",
                "You have received a job offer.",
            ),
            "hired": (
                "Application accepted",
                "Congratulations! You have been hired.",
            ),
            "rejected": (
                "Application rejected",
                "Your application has been rejected.",
            ),
            "withdrawn": (
                "Application withdrawn",
                "Your application has been withdrawn.",
            ),
            "reviewed": (
                "Application reviewed",
                "Your application has been reviewed.",
            ),
            "accepted": (
                "Application accepted",
                "Your application has been accepted.",
            ),
        }

        if new_status in notification_map:
            title, message = notification_map[
                new_status
            ]

            Notification.objects.create(
                user=application.applicant,
                notification_type=(
                    f"application_{new_status}"
                ),
                title=title,
                message=message,
                application=application,
                job=application.job,
            )

        return Response(
            {
                "detail": (
                    "Application status updated successfully."
                ),
                "application": self.get_serializer(
                    application
                ).data,
            }
        )


class InterviewViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Interview.objects.select_related(
                "application",
                "application__job",
                "application__job__company",
                "application__applicant",
                "scheduled_by",
            ).order_by(
                "-scheduled_at"
            )

        return Interview.objects.filter(
            Q(application__applicant=user)
            | Q(
                application__job__company__owner=user
            )
        ).select_related(
            "application",
            "application__job",
            "application__job__company",
            "application__applicant",
            "scheduled_by",
        ).order_by(
            "-scheduled_at"
        )

    def _is_employer(
        self,
        user,
        interview=None,
    ):
        if user.is_staff:
            return True

        if interview:
            return (
                interview.application.job.company.owner_id
                == user.id
            )

        return Company.objects.filter(
            owner=user
        ).exists()

    def _ensure_interview_employer_active(
        self,
        interview,
    ):
        ensure_company_owner_active(
            interview.application.job.company,
            self.request.user,
        )

    def _has_active_upcoming_interview(
        self,
        application,
        exclude_id=None,
    ):
        queryset = Interview.objects.filter(
            application=application,
            scheduled_at__gt=timezone.now(),
            status__in=[
                "scheduled",
                "rescheduled",
                "confirmed",
            ],
        )

        if exclude_id:
            queryset = queryset.exclude(
                id=exclude_id
            )

        return queryset.exists()

    def perform_create(self, serializer):
        application = serializer.validated_data.get(
            "application"
        )

        if not application:
            raise ValidationError(
                {
                    "application": (
                        "Application is required."
                    )
                }
            )

        job = application.job
        company = job.company

        if not self.request.user.is_staff:
            ensure_company_owner_active(
                company,
                self.request.user,
            )

        if (
            not self.request.user.is_staff
            and company.owner_id
            != self.request.user.id
        ):
            raise PermissionDenied(
                "You cannot schedule an interview for this application."
            )

        if application.status != "interview":
            raise ValidationError(
                {
                    "application": (
                        "The application must be in "
                        "the interview stage."
                    )
                }
            )

        scheduled_at = serializer.validated_data.get(
            "scheduled_at"
        )

        if not scheduled_at:
            raise ValidationError(
                {
                    "scheduled_at": (
                        "Interview date and time are required."
                    )
                }
            )

        if scheduled_at <= timezone.now():
            raise ValidationError(
                {
                    "scheduled_at": (
                        "Interview must be scheduled "
                        "for a future date and time."
                    )
                }
            )

        if self._has_active_upcoming_interview(
            application
        ):
            raise ValidationError(
                {
                    "application": (
                        "This application already has "
                        "an upcoming interview."
                    )
                }
            )

        interview = serializer.save(
            scheduled_by=self.request.user,
            status="scheduled",
        )

        Notification.objects.create(
            user=application.applicant,
            notification_type="interview_scheduled",
            title="Interview scheduled",
            message=(
                "An interview has been scheduled "
                f'for your application for "{job.title}".'
            ),
            application=application,
            job=job,
            interview=interview,
        )

    def perform_update(self, serializer):
        interview = self.get_object()

        if not self.request.user.is_staff:
            self._ensure_interview_employer_active(
                interview
            )

        if interview.status in [
            "cancelled",
            "completed",
            "declined",
        ]:
            raise ValidationError(
                {
                    "status": (
                        "This interview can no longer be modified."
                    )
                }
            )

        scheduled_at = serializer.validated_data.get(
            "scheduled_at"
        )

        if (
            scheduled_at
            and scheduled_at <= timezone.now()
        ):
            raise ValidationError(
                {
                    "scheduled_at": (
                        "Interview must be scheduled "
                        "for a future date and time."
                    )
                }
            )

        old_scheduled_at = interview.scheduled_at

        interview = serializer.save()

        if (
            scheduled_at
            and scheduled_at != old_scheduled_at
        ):
            interview.status = "rescheduled"
            interview.reschedule_requested = False

            interview.save(
                update_fields=[
                    "status",
                    "reschedule_requested",
                ]
            )

            Notification.objects.create(
                user=interview.application.applicant,
                notification_type="interview_rescheduled",
                title="Interview rescheduled",
                message=(
                    f'Your interview for '
                    f'"{interview.application.job.title}" '
                    "has been rescheduled."
                ),
                application=interview.application,
                job=interview.application.job,
                interview=interview,
            )

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            self._ensure_interview_employer_active(
                instance
            )

        instance.status = "cancelled"

        instance.save(
            update_fields=[
                "status"
            ]
        )

        Notification.objects.create(
            user=instance.application.applicant,
            notification_type="interview_cancelled",
            title="Interview cancelled",
            message=(
                f'Your interview for '
                f'"{instance.application.job.title}" '
                "has been cancelled."
            ),
            application=instance.application,
            job=instance.application.job,
            interview=instance,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def upcoming(self, request):
        queryset = self.get_queryset().filter(
            scheduled_at__gt=timezone.now(),
            status__in=[
                "scheduled",
                "rescheduled",
                "confirmed",
            ],
        )

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response(
            serializer.data
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def cancel(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if not request.user.is_staff:
            self._ensure_interview_employer_active(
                interview
            )

        if interview.status in [
            "cancelled",
            "completed",
            "declined",
        ]:
            raise ValidationError(
                {
                    "detail": (
                        "This interview cannot be cancelled."
                    )
                }
            )

        interview.status = "cancelled"

        interview.save(
            update_fields=[
                "status"
            ]
        )

        Notification.objects.create(
            user=interview.application.applicant,
            notification_type="interview_cancelled",
            title="Interview cancelled",
            message=(
                f'Your interview for '
                f'"{interview.application.job.title}" '
                "has been cancelled."
            ),
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Interview cancelled successfully."
                )
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def complete(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if not request.user.is_staff:
            self._ensure_interview_employer_active(
                interview
            )

        interview.status = "completed"

        interview.save(
            update_fields=[
                "status"
            ]
        )

        return Response(
            {
                "detail": (
                    "Interview marked as completed."
                ),
                "interview": self.get_serializer(
                    interview
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def confirm(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if (
            interview.application.applicant_id
            != request.user.id
        ):
            raise PermissionDenied(
                "Only the candidate can confirm this interview."
            )

        if interview.status in [
            "cancelled",
            "completed",
            "declined",
        ]:
            raise ValidationError(
                {
                    "detail": (
                        "This interview can no longer be confirmed."
                    )
                }
            )

        if interview.scheduled_at <= timezone.now():
            raise ValidationError(
                {
                    "detail": (
                        "This interview time has already passed."
                    )
                }
            )

        interview.attendance_status = "confirmed"
        interview.status = "confirmed"

        interview.save(
            update_fields=[
                "attendance_status",
                "status",
            ]
        )

        Notification.objects.create(
            user=interview.application.job.company.owner,
            notification_type="interview_confirmed",
            title="Interview confirmed",
            message=(
                f'The candidate has confirmed the interview '
                f'for "{interview.application.job.title}".'
            ),
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Interview confirmed successfully."
                ),
                "interview": self.get_serializer(
                    interview
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def request_reschedule(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if (
            interview.application.applicant_id
            != request.user.id
        ):
            raise PermissionDenied(
                "Only the candidate can request a reschedule."
            )

        if interview.status in [
            "cancelled",
            "completed",
            "declined",
        ]:
            raise ValidationError(
                {
                    "detail": (
                        "This interview cannot be rescheduled."
                    )
                }
            )

        preferred_date = request.data.get(
            "preferred_date"
        )

        preferred_time = request.data.get(
            "preferred_time"
        )

        reason = str(
            request.data.get(
                "reschedule_reason",
                "",
            )
        ).strip()

        if not preferred_date:
            raise ValidationError(
                {
                    "preferred_date": (
                        "Preferred date is required."
                    )
                }
            )

        if not preferred_time:
            raise ValidationError(
                {
                    "preferred_time": (
                        "Preferred time is required."
                    )
                }
            )

        if not reason:
            raise ValidationError(
                {
                    "reschedule_reason": (
                        "A reason is required."
                    )
                }
            )

        try:
            preferred_datetime = datetime.fromisoformat(
                f"{preferred_date}T{preferred_time}"
            )

            if timezone.is_naive(
                preferred_datetime
            ):
                preferred_datetime = timezone.make_aware(
                    preferred_datetime
                )

        except (
            TypeError,
            ValueError,
        ):
            raise ValidationError(
                {
                    "preferred_date": (
                        "Invalid date or time."
                    )
                }
            )

        if preferred_datetime <= timezone.now():
            raise ValidationError(
                {
                    "preferred_date": (
                        "The preferred interview time "
                        "must be in the future."
                    )
                }
            )

        interview.preferred_date = preferred_date
        interview.preferred_time = preferred_time
        interview.reschedule_reason = reason
        interview.reschedule_requested = True

        interview.save(
            update_fields=[
                "preferred_date",
                "preferred_time",
                "reschedule_reason",
                "reschedule_requested",
            ]
        )

        Notification.objects.create(
            user=interview.application.job.company.owner,
            notification_type="interview_reschedule_requested",
            title="Interview reschedule requested",
            message=(
                f'The candidate requested a new time '
                f'for the interview for '
                f'"{interview.application.job.title}".'
            ),
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Reschedule request submitted successfully."
                ),
                "interview": self.get_serializer(
                    interview
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def approve_reschedule(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if not request.user.is_staff:
            self._ensure_interview_employer_active(
                interview
            )

        if (
            not interview.reschedule_requested
            or not interview.preferred_date
            or not interview.preferred_time
        ):
            raise ValidationError(
                {
                    "detail": (
                        "There is no pending reschedule request."
                    )
                }
            )

        try:
            preferred_datetime = datetime.fromisoformat(
                f"{interview.preferred_date}T"
                f"{interview.preferred_time}"
            )

            if timezone.is_naive(
                preferred_datetime
            ):
                preferred_datetime = timezone.make_aware(
                    preferred_datetime
                )

        except (
            TypeError,
            ValueError,
        ):
            raise ValidationError(
                {
                    "detail": (
                        "The requested date or time is invalid."
                    )
                }
            )

        if preferred_datetime <= timezone.now():
            raise ValidationError(
                {
                    "detail": (
                        "The requested interview time "
                        "must be in the future."
                    )
                }
            )

        if self._has_active_upcoming_interview(
            interview.application,
            exclude_id=interview.id,
        ):
            raise ValidationError(
                {
                    "detail": (
                        "Another upcoming interview already "
                        "exists for this application."
                    )
                }
            )

        interview.scheduled_at = preferred_datetime
        interview.status = "rescheduled"
        interview.reschedule_requested = False

        interview.save(
            update_fields=[
                "scheduled_at",
                "status",
                "reschedule_requested",
            ]
        )

        Notification.objects.create(
            user=interview.application.applicant,
            notification_type="interview_reschedule_approved",
            title="Reschedule approved",
            message=(
                f'Your requested new interview time for '
                f'"{interview.application.job.title}" '
                "has been approved."
            ),
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Reschedule approved successfully."
                ),
                "interview": self.get_serializer(
                    interview
                ).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def reject_reschedule(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if not request.user.is_staff:
            self._ensure_interview_employer_active(
                interview
            )

        if not interview.reschedule_requested:
            raise ValidationError(
                {
                    "detail": (
                        "There is no pending reschedule request."
                    )
                }
            )

        message = str(
            request.data.get(
                "message",
                "",
            )
        ).strip()

        interview.reschedule_requested = False
        interview.preferred_date = None
        interview.preferred_time = None
        interview.reschedule_reason = ""

        interview.save(
            update_fields=[
                "reschedule_requested",
                "preferred_date",
                "preferred_time",
                "reschedule_reason",
            ]
        )

        notification_message = (
            f'Your reschedule request for '
            f'"{interview.application.job.title}" '
            "has been rejected."
        )

        if message:
            notification_message += (
                f" Message: {message}"
            )

        Notification.objects.create(
            user=interview.application.applicant,
            notification_type="interview_reschedule_rejected",
            title="Reschedule rejected",
            message=notification_message,
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Reschedule request rejected."
                )
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def decline(
        self,
        request,
        pk=None,
    ):
        interview = self.get_object()

        if (
            interview.application.applicant_id
            != request.user.id
        ):
            raise PermissionDenied(
                "Only the candidate can decline this interview."
            )

        if interview.status in [
            "cancelled",
            "completed",
            "declined",
        ]:
            raise ValidationError(
                {
                    "detail": (
                        "This interview cannot be declined."
                    )
                }
            )

        response = str(
            request.data.get(
                "response",
                "",
            )
        ).strip()

        interview.status = "declined"
        interview.candidate_response = response

        interview.save(
            update_fields=[
                "status",
                "candidate_response",
            ]
        )

        Notification.objects.create(
            user=interview.application.job.company.owner,
            notification_type="interview_declined",
            title="Interview declined",
            message=(
                f'The candidate declined the interview '
                f'for "{interview.application.job.title}".'
            ),
            application=interview.application,
            job=interview.application.job,
            interview=interview,
        )

        return Response(
            {
                "detail": (
                    "Interview declined successfully."
                )
            }
        )


class SavedJobViewSet(viewsets.ModelViewSet):
    serializer_class = SavedJobSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        return SavedJob.objects.filter(
            user=self.request.user
        ).select_related(
            "job",
            "job__company",
        ).order_by(
            "-id"
        )

    def perform_create(self, serializer):
        user = self.request.user

        if Company.objects.filter(
            owner=user
        ).exists():
            raise PermissionDenied(
                "Employers cannot save jobs."
            )

        job = serializer.validated_data.get(
            "job"
        )

        if not job:
            raise ValidationError(
                {
                    "job": "Job is required."
                }
            )

        if not job.is_approved:
            raise ValidationError(
                {
                    "job": "This job is not approved."
                }
            )

        if job.status != "open":
            raise ValidationError(
                {
                    "job": "This job is closed."
                }
            )

        if SavedJob.objects.filter(
            user=user,
            job=job,
        ).exists():
            raise ValidationError(
                {
                    "detail": (
                        "You have already saved this job."
                    )
                }
            )

        serializer.save(
            user=user
        )

    def perform_update(self, serializer):
        saved_job = self.get_object()

        if saved_job.user_id != self.request.user.id:
            raise PermissionDenied(
                "You do not have permission to modify this saved job."
            )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied(
                "You do not have permission to delete this saved job."
            )

        instance.delete()


class ProfileView(APIView):
    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):
        UserProfile.objects.get_or_create(
            user=request.user
        )

        serializer = ProfileSerializer(
            request.user,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data
        )

    def patch(self, request):
        user = request.user

        profile, _ = UserProfile.objects.get_or_create(
            user=user
        )

        data = request.data.copy()

        profile_photo = data.get(
            "profile_photo"
        )

        if profile_photo:
            last_changed = (
                profile.profile_photo_updated_at
            )

            if last_changed:
                cooldown = timedelta(
                    hours=24
                )

                if (
                    timezone.now() - last_changed
                    < cooldown
                ):
                    raise ValidationError(
                        {
                            "profile_photo": (
                                "You can only change your "
                                "profile photo once every 24 hours."
                            )
                        }
                    )

            content_type = getattr(
                profile_photo,
                "content_type",
                "",
            )

            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/webp",
            ]

            if content_type not in allowed_types:
                raise ValidationError(
                    {
                        "profile_photo": (
                            "Only JPG, PNG and WEBP images are allowed."
                        )
                    }
                )

            if profile_photo.size > 5 * 1024 * 1024:
                raise ValidationError(
                    {
                        "profile_photo": (
                            "Profile photo must be smaller than 5MB."
                        )
                    }
                )

        if (
            "resume" in data
            and Company.objects.filter(
                owner=user
            ).exists()
        ):
            raise ValidationError(
                {
                    "resume": (
                        "Employers cannot upload resumes."
                    )
                }
            )

        username = data.get(
            "username"
        )

        if username:
            username = str(
                username
            ).strip()

            if User.objects.filter(
                username__iexact=username
            ).exclude(
                id=user.id
            ).exists():
                raise ValidationError(
                    {
                        "username": (
                            "Username already exists."
                        )
                    }
                )

            data["username"] = username

        with transaction.atomic():
            user_serializer = ProfileSerializer(
                user,
                data=data,
                partial=True,
                context={
                    "request": request
                },
            )

            user_serializer.is_valid(
                raise_exception=True
            )

            user_serializer.save()

            if profile_photo:
                profile.profile_photo_updated_at = (
                    timezone.now()
                )

                profile.save(
                    update_fields=[
                        "profile_photo_updated_at"
                    ]
                )

        serializer = ProfileSerializer(
            user,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data
        )


class PublicProfileView(APIView):
    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        username,
    ):
        try:
            user = User.objects.get(
                username__iexact=username
            )

        except User.DoesNotExist:
            return Response(
                {
                    "detail": (
                        "User profile not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        profile, _ = UserProfile.objects.get_or_create(
            user=user
        )

        if (
            user.id != request.user.id
            and not profile.is_public
        ):
            return Response(
                {
                    "detail": (
                        "This profile is private."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            user.id != request.user.id
            and Company.objects.filter(
                owner=user
            ).exists()
        ):
            company = Company.objects.filter(
                owner=user
            ).first()

            if (
                not company.is_active
                or company.is_suspended
            ):
                return Response(
                    {
                        "detail": (
                            "This employer profile is unavailable."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = PublicProfileSerializer(
            user,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data
        )


class AdminDashboardView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(self, request):
        return Response(
            {
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(
                    is_active=True
                ).count(),
                "inactive_users": User.objects.filter(
                    is_active=False
                ).count(),
                "total_companies": Company.objects.count(),
                "active_companies": Company.objects.filter(
                    is_active=True
                ).count(),
                "inactive_companies": Company.objects.filter(
                    is_active=False
                ).count(),
                "suspended_companies": Company.objects.filter(
                    is_suspended=True
                ).count(),
                "total_jobs": Job.objects.count(),
                "total_applications": Application.objects.count(),
                "pending_jobs": Job.objects.filter(
                    moderation_status="pending"
                ).count(),
                "approved_jobs": Job.objects.filter(
                    is_approved=True
                ).count(),
            }
        )


class AdminUsersView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(self, request):
        users = User.objects.all().order_by(
            "-date_joined"
        )

        data = []

        for user in users:
            companies = Company.objects.filter(
                owner=user
            )

            data.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "is_staff": user.is_staff,
                    "is_active": user.is_active,
                    "date_joined": user.date_joined,
                    "is_employer": companies.exists(),
                    "company_count": companies.count(),
                    "has_suspended_company": companies.filter(
                        is_suspended=True
                    ).exists(),
                    "companies": CompanySerializer(
                        companies,
                        many=True,
                        context={
                            "request": request
                        },
                    ).data,
                }
            )

        return Response(data)

    def patch(
        self,
        request,
        user_id,
    ):
        try:
            user = User.objects.get(
                id=user_id
            )

        except User.DoesNotExist:
            return Response(
                {
                    "detail": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_staff:
            return Response(
                {
                    "detail": (
                        "Administrator accounts cannot be modified here."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if "is_active" not in request.data:
            return Response(
                {
                    "detail": (
                        "Only is_active can be changed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        value = parse_boolean(
            request.data.get(
                "is_active"
            )
        )

        old_status = user.is_active

        if old_status == value:
            return Response(
                {
                    "detail": (
                        "User status is already set to this value."
                    ),
                    "is_active": user.is_active,
                }
            )

        user.is_active = value

        user.save(
            update_fields=[
                "is_active"
            ]
        )

        if not user.is_active:
            Token.objects.filter(
                user=user
            ).delete()

            log_admin_activity(
                request.user,
                user,
                CHANGE,
                "User account deactivated by administrator.",
            )

            return Response(
                {
                    "detail": (
                        "User account deactivated successfully."
                    ),
                    "is_active": False,
                }
            )

        Token.objects.get_or_create(
            user=user
        )

        log_admin_activity(
            request.user,
            user,
            CHANGE,
            "User account reactivated by administrator.",
        )

        return Response(
            {
                "detail": (
                    "User account reactivated successfully."
                ),
                "is_active": True,
            }
        )

    def delete(
        self,
        request,
        user_id,
    ):
        try:
            user = User.objects.get(
                id=user_id
            )

        except User.DoesNotExist:
            return Response(
                {
                    "detail": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_staff:
            return Response(
                {
                    "detail": (
                        "Administrator accounts cannot be deleted."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.id == request.user.id:
            return Response(
                {
                    "detail": (
                        "You cannot delete your own administrator account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        username = user.username

        with transaction.atomic():
            Token.objects.filter(
                user=user
            ).delete()

            log_admin_activity(
                request.user,
                user,
                DELETION,
                (
                    "User account permanently deleted by administrator. "
                    f"Username: {username}"
                ),
            )

            user.delete()

        return Response(
            {
                "detail": (
                    "User and all related data were permanently deleted."
                )
            },
            status=status.HTTP_200_OK,
        )


class AdminCompaniesView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(self, request):
        companies = Company.objects.all().select_related(
            "owner"
        ).order_by(
            "-created_at"
        )

        serializer = CompanySerializer(
            companies,
            many=True,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data
        )

    def patch(
        self,
        request,
        company_id,
    ):
        try:
            company = Company.objects.select_related(
                "owner"
            ).get(
                id=company_id
            )

        except Company.DoesNotExist:
            return Response(
                {
                    "detail": "Company not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        allowed_fields = {
            "is_active",
            "is_suspended",
            "suspension_reason",
        }

        supplied_fields = set(
            request.data.keys()
        )

        unsupported_fields = (
            supplied_fields - allowed_fields
        )

        if unsupported_fields:
            raise ValidationError(
                {
                    "detail": (
                        "Only is_active, is_suspended "
                        "and suspension_reason can be changed."
                    )
                }
            )

        old_is_active = company.is_active
        old_is_suspended = company.is_suspended
        old_reason = getattr(
            company,
            "suspension_reason",
            "",
        )

        new_is_active = company.is_active
        new_is_suspended = company.is_suspended
        new_reason = old_reason

        if "is_active" in request.data:
            new_is_active = parse_boolean(
                request.data.get(
                    "is_active"
                )
            )

        if "is_suspended" in request.data:
            new_is_suspended = parse_boolean(
                request.data.get(
                    "is_suspended"
                )
            )

        if "suspension_reason" in request.data:
            new_reason = str(
                request.data.get(
                    "suspension_reason",
                    "",
                )
            ).strip()

        if (
            new_is_suspended
            and not new_reason
        ):
            raise ValidationError(
                {
                    "suspension_reason": (
                        "A suspension reason is required "
                        "when suspending a company."
                    )
                }
            )

        if not new_is_suspended:
            new_reason = ""

        changed_fields = []

        if new_is_active != old_is_active:
            company.is_active = new_is_active
            changed_fields.append(
                "is_active"
            )

        if new_is_suspended != old_is_suspended:
            company.is_suspended = new_is_suspended
            changed_fields.append(
                "is_suspended"
            )

        if new_reason != old_reason:
            company.suspension_reason = new_reason
            changed_fields.append(
                "suspension_reason"
            )

        if not changed_fields:
            return Response(
                {
                    "detail": (
                        "No company status changes were made."
                    ),
                    "is_active": company.is_active,
                    "is_suspended": company.is_suspended,
                    "suspension_reason": getattr(
                        company,
                        "suspension_reason",
                        "",
                    ),
                }
            )

        company.save(
            update_fields=list(
                dict.fromkeys(
                    changed_fields
                )
            )
        )

        if (
            not old_is_suspended
            and company.is_suspended
        ):
            Notification.objects.create(
                user=company.owner,
                notification_type="company_suspended",
                title="Company suspended",
                message=(
                    f'Your company "{company.name}" '
                    "has been suspended by an administrator. "
                    f"Reason: {company.suspension_reason}"
                ),
            )

            log_admin_activity(
                request.user,
                company,
                CHANGE,
                (
                    "Company suspended by administrator. "
                    f"Reason: {company.suspension_reason}"
                ),
            )

        elif (
            old_is_suspended
            and not company.is_suspended
        ):
            Notification.objects.create(
                user=company.owner,
                notification_type="company_reactivated",
                title="Company reactivated",
                message=(
                    f'Your company "{company.name}" '
                    "has been reactivated by an administrator. "
                    "You can now use employer features again."
                ),
            )

            log_admin_activity(
                request.user,
                company,
                CHANGE,
                "Company reactivated by administrator.",
            )

        elif (
            old_reason
            != company.suspension_reason
            and company.is_suspended
        ):
            Notification.objects.create(
                user=company.owner,
                notification_type="company_suspended",
                title="Suspension updated",
                message=(
                    f'The suspension of your company '
                    f'"{company.name}" has been updated. '
                    f"Reason: {company.suspension_reason}"
                ),
            )

            log_admin_activity(
                request.user,
                company,
                CHANGE,
                (
                    "Company suspension reason updated. "
                    f"Reason: {company.suspension_reason}"
                ),
            )

        if (
            old_is_active
            and not company.is_active
        ):
            log_admin_activity(
                request.user,
                company,
                CHANGE,
                "Company deactivated by administrator.",
            )

        elif (
            not old_is_active
            and company.is_active
        ):
            log_admin_activity(
                request.user,
                company,
                CHANGE,
                "Company reactivated from inactive state by administrator.",
            )

        return Response(
            {
                "detail": (
                    "Company status updated successfully."
                ),
                "is_active": company.is_active,
                "is_suspended": company.is_suspended,
                "suspension_reason": getattr(
                    company,
                    "suspension_reason",
                    "",
                ),
            }
        )

    def delete(
        self,
        request,
        company_id,
    ):
        try:
            company = Company.objects.select_related(
                "owner"
            ).get(
                id=company_id
            )

        except Company.DoesNotExist:
            return Response(
                {
                    "detail": "Company not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        company_name = company.name
        owner_username = company.owner.username

        with transaction.atomic():
            log_admin_activity(
                request.user,
                company,
                DELETION,
                (
                    "Company permanently deleted by administrator. "
                    f"Company: {company_name}. "
                    f"Owner: {owner_username}."
                ),
            )

            company.delete()

        return Response(
            {
                "detail": (
                    f'Company "{company_name}" and all related '
                    "jobs, applications and company data were "
                    "permanently deleted. The employer user account "
                    "remains active."
                )
            },
            status=status.HTTP_200_OK,
        )


class AdminApplicationsView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(self, request):
        applications = Application.objects.all().select_related(
            "job",
            "job__company",
            "applicant",
            "resume",
        ).order_by(
            "-applied_at"
        )

        serializer = ApplicationSerializer(
            applications,
            many=True,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = str(
        request.data.get(
            "email",
            "",
        )
    ).strip().lower()

    if not email:
        return Response(
            {
                "detail": "Email is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(
            email__iexact=email
        )

    except User.DoesNotExist:
        return Response(
            {
                "detail": (
                    "No account was found with this email."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    uid = urlsafe_base64_encode(
        force_bytes(user.pk)
    )

    token = default_token_generator.make_token(
        user
    )

    return Response(
        {
            "detail": (
                "Password reset token generated successfully."
            ),
            "uid": uid,
            "token": token,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uid = str(
        request.data.get(
            "uid",
            "",
        )
    )

    token = str(
        request.data.get(
            "token",
            "",
        )
    )

    password = str(
        request.data.get(
            "password",
            "",
        )
    )

    if not uid or not token or not password:
        return Response(
            {
                "detail": (
                    "uid, token and password are required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return Response(
            {
                "detail": (
                    "Password must be at least 8 characters long."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_id = force_str(
            urlsafe_base64_decode(uid)
        )

        user = User.objects.get(
            pk=user_id
        )

    except (
        TypeError,
        ValueError,
        OverflowError,
        User.DoesNotExist,
    ):
        return Response(
            {
                "detail": (
                    "Invalid password reset link."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not default_token_generator.check_token(
        user,
        token,
    ):
        return Response(
            {
                "detail": (
                    "Invalid or expired password reset token."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(
        password
    )

    user.save(
        update_fields=[
            "password"
        ]
    )

    Token.objects.filter(
        user=user
    ).delete()

    return Response(
        {
            "detail": (
                "Password reset successfully."
            )
        }
    )


class NotificationViewSet(
    viewsets.ReadOnlyModelViewSet
):
    serializer_class = NotificationSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by(
            "-created_at"
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def mark_read(
        self,
        request,
        pk=None,
    ):
        notification = self.get_object()

        notification.is_read = True

        notification.save(
            update_fields=[
                "is_read"
            ]
        )

        return Response(
            {
                "detail": (
                    "Notification marked as read."
                )
            }
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def mark_all_read(
        self,
        request,
    ):
        Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(
            is_read=True
        )

        return Response(
            {
                "detail": (
                    "All notifications marked as read."
                )
            }
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def unread_count(
        self,
        request,
    ):
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        return Response(
            {
                "unread_count": count
            }
        )


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Conversation.objects.all().prefetch_related(
                "participants",
                "messages"
            ).order_by(
                "-updated_at"
            )

        return Conversation.objects.filter(
            participants=user
        ).prefetch_related(
            "participants",
            "messages"
        ).order_by(
            "-updated_at"
        )

    def perform_create(self, serializer):
        user = self.request.user

        participant_ids = self.request.data.get(
            "participant_ids",
            []
        )

        subject = str(
            self.request.data.get(
                "subject",
                ""
            )
        ).strip()

        message = str(
            self.request.data.get(
                "message",
                ""
            )
        ).strip()

        if not subject:
            raise ValidationError(
                {
                    "subject": (
                        "Subject is required."
                    )
                }
            )

        if not message:
            raise ValidationError(
                {
                    "message": (
                        "Message is required."
                    )
                }
            )

        if not isinstance(
            participant_ids,
            list
        ):
            raise ValidationError(
                {
                    "participant_ids": (
                        "participant_ids must be a list."
                    )
                }
            )

        participant_ids = list(
            set(participant_ids)
        )

        users = list(
            User.objects.filter(
                id__in=participant_ids,
                is_active=True
            )
        )

        if not users:
            raise ValidationError(
                {
                    "participant_ids": (
                        "At least one valid participant "
                        "is required."
                    )
                }
            )

        if user not in users:
            users.append(user)

        with transaction.atomic():
            conversation = serializer.save()

            conversation.participants.add(
                *users
            )

            Message.objects.create(
                conversation=conversation,
                sender=user,
                message=message
            )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def messages(
        self,
        request,
        pk=None
    ):
        conversation = self.get_object()

        messages = Message.objects.filter(
            conversation=conversation
        ).select_related(
            "sender"
        ).order_by(
            "created_at"
        )

        messages.filter(
            ~Q(sender=request.user),
            is_read=False
        ).update(
            is_read=True
        )

        serializer = MessageSerializer(
            messages,
            many=True,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated]
    )
    def send_message(
        self,
        request,
        pk=None
    ):
        conversation = self.get_object()

        content = str(
            request.data.get(
                "message",
                request.data.get(
                    "content",
                    ""
                )
            )
        ).strip()

        if not content:
            raise ValidationError(
                {
                    "message": (
                        "Message cannot be empty."
                    )
                }
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message=content
        )

        conversation.save(
            update_fields=[
                "updated_at"
            ]
        )

        serializer = MessageSerializer(
            message,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated]
    )
    def close(
        self,
        request,
        pk=None
    ):
        conversation = self.get_object()

        conversation.status = "closed"

        conversation.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        return Response(
            {
                "detail": (
                    "Conversation closed successfully."
                )
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated]
    )
    def reopen(
        self,
        request,
        pk=None
    ):
        conversation = self.get_object()

        conversation.status = "open"

        conversation.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        return Response(
            {
                "detail": (
                    "Conversation reopened successfully."
                )
            }
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def unread_count(
        self,
        request
    ):
        count = Message.objects.filter(
            conversation__participants=request.user,
            is_read=False
        ).exclude(
            sender=request.user
        ).distinct().count()

        return Response(
            {
                "unread_count": count
            }
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def user_search(
        self,
        request
    ):
        search = str(
            request.query_params.get(
                "search",
                ""
            )
        ).strip()

        if len(search) < 2:
            return Response([])

        users = User.objects.filter(
            is_active=True
        ).exclude(
            id=request.user.id
        ).filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        ).order_by(
            "first_name",
            "last_name",
            "username"
        )[:20]

        results = []

        for user in users:
            full_name = user.get_full_name().strip()

            profile_photo = None

            try:
                if user.profile.profile_photo:
                    profile_photo = request.build_absolute_uri(
                        user.profile.profile_photo.url
                    )
            except UserProfile.DoesNotExist:
                pass

            results.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": full_name or user.username,
                    "profile_photo": profile_photo,
                }
            )

        return Response(
            results
        )