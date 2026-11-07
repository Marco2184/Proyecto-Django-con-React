# Generated manually for Monolith discount coupons

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carrito', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrito',
            name='codigo_cupon',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
