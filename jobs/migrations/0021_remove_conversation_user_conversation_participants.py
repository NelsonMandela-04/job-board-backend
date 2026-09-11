from django.conf import settings
from django.db import migrations, models


def copy_conversation_users_to_participants(apps, schema_editor):
    Conversation = apps.get_model("jobs", "Conversation")

    for conversation in Conversation.objects.all().iterator():
        if conversation.user_id:
            conversation.participants.add(conversation.user_id)


class Migration(migrations.Migration):

    dependencies = [
        (
            "jobs",
            "0020_company_suspended_at_company_suspended_by_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="participants",
            field=models.ManyToManyField(
                related_name="conversations_temp",
                to=settings.AUTH_USER_MODEL,
                blank=True,
            ),
        ),
        migrations.RunPython(
            copy_conversation_users_to_participants,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="conversation",
            name="user",
        ),
        migrations.AlterField(
            model_name="conversation",
            name="participants",
            field=models.ManyToManyField(
                related_name="conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]