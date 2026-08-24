from django.db import migrations, models
from apps.accounts.choices import AuthType  # مسیر درست را بررسی کنید

def set_auth_type_based_on_session(apps, schema_editor):
    DeviceSession = apps.get_model('accounts', 'DeviceSession')
    
    for session in DeviceSession.objects.all():
        if session.django_session_key:
            session.auth_type = AuthType.WEB  # اگر WEB یک رشته است
        elif session.refresh_token_jti:
            session.auth_type = AuthType.API
        else:
            session.auth_type = AuthType.WEB
        session.save()

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_devicesession'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicesession',
            name='auth_type',
            field=models.CharField(
                max_length=10,
                choices=AuthType.choices,
                null=True,
            ),
        ),
        migrations.RunPython(set_auth_type_based_on_session),
        migrations.AlterField(
            model_name='devicesession',
            name='auth_type',
            field=models.CharField(
                max_length=10,
                choices=AuthType.choices,
            ),
        ),
    ]