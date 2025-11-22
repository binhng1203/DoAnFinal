from django.db import migrations, models
import src.apps.core.models  # Dùng để import UserManager
import uuid

class Migration(migrations.Migration):

    initial = True

    # Phụ thuộc vào app 'auth' vì User model dùng PermissionsMixin
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('permission_id', models.AutoField(db_column='permission_id', primary_key=True, serialize=False)),
                ('permission_key', models.CharField(db_column='permission_key', max_length=100, unique=True)),
                ('description', models.TextField(blank=True, db_column='description', null=True)),
            ],
            options={
                'db_table': '"core"."permissions"',
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('role_id', models.AutoField(db_column='role_id', primary_key=True, serialize=False)),
                ('role_name', models.CharField(db_column='role_name', max_length=50, unique=True)),
                ('description', models.TextField(blank=True, db_column='description', null=True)),
            ],
            options={
                'db_table': '"core"."roles"',
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('user_id', models.UUIDField(db_column='user_id', default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('fullname', models.CharField(db_column='fullname', max_length=100, unique=True)),
                ('username', models.CharField(db_column='username', max_length=100, unique=True)),
                ('email', models.EmailField(db_column='email', max_length=255, unique=True)),
                ('password', models.CharField(db_column='password_hash', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('is_active', models.BooleanField(db_column='is_active', default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'db_table': '"core"."users"',
            },
            managers=[
                ('objects', src.apps.core.models.UserManager()),
            ],
        ),
    ]