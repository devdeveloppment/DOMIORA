# Generated manually to fix PropertyDocument foreign key issue

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0011_propertydocument_alter_property_is_published_and_more'),
    ]

    operations = [
        # Check if table exists and recreate with correct schema
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS properties_propertydocument",
            reverse_sql="DROP TABLE IF EXISTS properties_propertydocument"
        ),
        # Recreate the table with correct schema
        migrations.CreateModel(
            name='PropertyDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(help_text='PDF, JPG, PNG, DOC autorisés', upload_to='properties/documents/%Y/%m/')),
                ('document_type', models.CharField(choices=[('titre_propriete', 'Titre de propriété'), ('plan', 'Plan/Schéma'), ('certificat_construction', 'Certificat de construction'), ('facture_services', 'Factures services (eau, électricité)'), ('diagnostique', 'Diagnostique/Inspection'), ('contrat_location', 'Contrat de location'), ('autre', 'Autre document')], default='autre', max_length=30)),
                ('title', models.CharField(help_text='Titre du document', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Description optionnelle')),
                ('order', models.PositiveSmallIntegerField(default=0, help_text="Ordre d'affichage")),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('related_property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='properties.property')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Property Documents',
                'ordering': ['order', '-uploaded_at'],
            },
        ),
    ]