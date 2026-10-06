from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_settings", "0004_alter_sitesettings_contact_phone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="contact_email",
            field=models.EmailField(
                default="denistchil@gmail.com",
                max_length=254,
            ),
        ),
    ]
