from django.db import migrations

def seed(apps,schema_editor):
    Promotion=apps.get_model('carrito','Promotion')
    for code,kind,value in [('MONOLITH10','porcentaje','10.00'),('GAMER20','porcentaje','20.00'),('NEON50','fijo','50.00')]:
        Promotion.objects.get_or_create(codigo=code,defaults={'tipo':kind,'valor':value})

class Migration(migrations.Migration):
    dependencies=[('carrito','0003_promotions_checkout')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
