from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_settings", "0003_alter_sitesettings_tagline"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="contact_phone",
            field=models.CharField(
                default="+228 90 56 78 48 / +228 73 06 01 18",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="address",
            field=models.CharField(default="Lomé, Togo", max_length=255),
        ),
    ]
