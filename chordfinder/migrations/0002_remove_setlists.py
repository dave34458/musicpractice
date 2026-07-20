from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chordfinder', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SetlistEntry',
        ),
        migrations.DeleteModel(
            name='Setlist',
        ),
    ]
