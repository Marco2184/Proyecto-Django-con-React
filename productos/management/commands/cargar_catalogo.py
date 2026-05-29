"""
Carga el catálogo completo de Monolith:
  - JUEGOS: importados desde la API de RAWG (https://rawg.io)
  - CONSOLAS y PERIFÉRICOS: dataset curado con imágenes de CDN público

Mantiene las categorías existentes (Juegos, Consolas, Accesorios).

Uso:
    python manage.py cargar_catalogo
    python manage.py cargar_catalogo --juegos 40
    python manage.py cargar_catalogo --solo-hardware
"""
import random, urllib.request, urllib.parse, json, os
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from productos.models import Producto, Categoria, Plataforma


def _api_key():
    env_file = Path(settings.BASE_DIR) / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k.strip() == 'RAWG_API_KEY':
                return v.strip()
    return os.environ.get('RAWG_API_KEY', '')


ADULT_BLOCKLIST = {
    'erotic', 'erótico', 'erotico', 'sex', 'sexual', 'hentai', 'nsfw',
    'porn', 'porno', 'pornographic', 'adult only', 'adult-only', 'adults only', 'ao rated',
    'mature sexual', 'explicit', 'sexual-content', 'nudity', 'nude', 'naked', 'desnudo',
    'strip', 'stripper', 'seduce', 'seduction', 'succubus', 'brothel', 'waifu',
    'dating sim', 'visual novel adult', '18+', '+18', 'r18', 'uncensored',
}

def is_adult_game(juego):
    """Evita importar juegos eróticos/adultos desde RAWG."""
    text_parts = [juego.get('name', ''), juego.get('slug', ''), juego.get('description_raw', '')]
    for collection in ('tags', 'genres'):
        for item in juego.get(collection, []) or []:
            text_parts.extend([item.get('name', ''), item.get('slug', '')])
    esrb = juego.get('esrb_rating') or {}
    text_parts.extend([esrb.get('name', ''), esrb.get('slug', '')])
    text = ' '.join(str(x).lower() for x in text_parts if x)
    return any(term in text for term in ADULT_BLOCKLIST)


MAPEO_PLATAFORMAS = {
    'pc': 'PC',
    'playstation5': 'PlayStation 5',
    'playstation4': 'PlayStation 5',  # Contar PS4 como PS5
    'xbox-series-x': 'Xbox Series X',
    'xbox-one': 'Xbox Series X',  # Contar Xbox One como Series X
    'nintendo-switch': 'Nintendo Switch',
}

# Solo estas consolas
CONSOLAS_PERMITIDAS = {'PC', 'PlayStation 5', 'Xbox Series X', 'Nintendo Switch'}

CONSOLAS = [
    {'nombre':'PlayStation 5 Slim','precio':2299.00,'precio_original':2599.00,'stock':12,
     'plataformas':['PlayStation 5'],
     'descripcion':'Consola PlayStation 5 versión Slim con lector de discos. SSD ultrarrápido y gráficos 4K.',
     'imagen':'https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=600',
     'specs':{'Almacenamiento':'1TB SSD','Resolución':'4K / 120Hz','CPU':'AMD Zen 2','Color':'Blanco'},'ventas':540},
    {'nombre':'Xbox Series X','precio':2399.00,'precio_original':None,'stock':9,
     'plataformas':['Xbox Series X'],
     'descripcion':'La consola Xbox más potente. 12 teraflops de poder gráfico.',
     'imagen':'https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=600',
     'specs':{'Almacenamiento':'1TB NVMe SSD','Resolución':'4K / 120Hz','GPU':'12 TFLOPS','Color':'Negro'},'ventas':410},
    {'nombre':'Nintendo Switch OLED','precio':1599.00,'precio_original':1799.00,'stock':20,
     'plataformas':['Nintendo Switch'],
     'descripcion':'Nintendo Switch con pantalla OLED de 7 pulgadas. Modo portátil y TV.',
     'imagen':'https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?w=600',
     'specs':{'Pantalla':'7" OLED','Almacenamiento':'64GB','Batería':'4.5-9 horas','Color':'Blanco'},'ventas':680},
    {'nombre':'PlayStation 5 Digital Edition','precio':1899.00,'precio_original':None,'stock':7,
     'plataformas':['PlayStation 5'],
     'descripcion':'PlayStation 5 sin lector de discos. Totalmente digital, más ligera y económica.',
     'imagen':'https://images.unsplash.com/photo-1607853202273-797f1c22a38e?w=600',
     'specs':{'Almacenamiento':'825GB SSD','Resolución':'4K','Tipo':'Digital','Color':'Blanco'},'ventas':320},
]

PERIFERICOS = [
    {'nombre':'Control DualSense PS5','precio':329.00,'precio_original':379.00,'stock':35,
     'plataformas':['PlayStation 5'],
     'descripcion':'Control inalámbrico DualSense con retroalimentación háptica y gatillos adaptativos.',
     'imagen':'https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=600',
     'specs':{'Conectividad':'Bluetooth / USB-C','Batería':'12 horas','Peso':'280g'},'ventas':720},
    {'nombre':'Audífonos Gaming HyperX Cloud','precio':449.00,'precio_original':549.00,'stock':28,
     'plataformas':['PC','PlayStation 5','Xbox Series X'],
     'descripcion':'Audífonos gaming con sonido envolvente 7.1 y micrófono con cancelación de ruido.',
     'imagen':'https://images.unsplash.com/photo-1599669454699-248893623440?w=600',
     'specs':{'Audio':'7.1 Surround','Driver':'53mm','Micrófono':'Desmontable','Conexión':'USB / 3.5mm'},'ventas':590},
    {'nombre':'Teclado Mecánico RGB Pro','precio':389.00,'precio_original':None,'stock':22,
     'plataformas':['PC'],
     'descripcion':'Teclado mecánico gaming con switches rojos, iluminación RGB y reposamuñecas.',
     'imagen':'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600',
     'specs':{'Switches':'Mecánicos Rojos','Iluminación':'RGB','Layout':'Español','Anti-ghosting':'Sí'},'ventas':450},
    {'nombre':'Mouse Gaming Inalámbrico 16K DPI','precio':279.00,'precio_original':329.00,'stock':40,
     'plataformas':['PC'],
     'descripcion':'Mouse gaming inalámbrico ultraligero con sensor óptico de 16,000 DPI.',
     'imagen':'https://images.unsplash.com/photo-1527814050087-3793815479db?w=600',
     'specs':{'Sensor':'16,000 DPI','Peso':'63g','Batería':'70 horas','Botones':'6 programables'},'ventas':510},
    {'nombre':'Control Xbox Wireless','precio':299.00,'precio_original':None,'stock':30,
     'plataformas':['Xbox Series X','PC'],
     'descripcion':'Control inalámbrico Xbox con agarre texturizado y botón compartir.',
     'imagen':'https://images.unsplash.com/photo-1612801798930-288967b6d1ef?w=600',
     'specs':{'Conectividad':'Bluetooth / USB-C','Batería':'AA / Recargable','Compatibilidad':'Xbox / PC'},'ventas':380},
    {'nombre':'Silla Gamer Ergonómica','precio':899.00,'precio_original':1099.00,'stock':14,
     'plataformas':['PC'],
     'descripcion':'Silla gaming ergonómica con soporte lumbar, reposabrazos 4D y reclinable 180°.',
     'imagen':'https://images.unsplash.com/photo-1598550476439-6847785fcea6?w=600',
     'specs':{'Material':'Cuero PU','Reclinación':'90-180°','Peso máx':'150kg','Reposabrazos':'4D'},'ventas':260},
]


class Command(BaseCommand):
    help = 'Carga el catálogo: juegos desde RAWG + consolas y periféricos curados'

    def add_arguments(self, parser):
        parser.add_argument('--juegos', type=int, default=30,
                            help='Cantidad de juegos a importar desde RAWG (default 30)')
        parser.add_argument('--solo-hardware', action='store_true',
                            help='Carga solo consolas y periféricos, sin llamar a la API')

    def handle(self, *args, **opts):
        # ── Categorías base (no se modifican si existen) ──
        cat_juegos, _     = Categoria.objects.get_or_create(nombre='Juegos')
        cat_consolas, _   = Categoria.objects.get_or_create(nombre='Consolas')
        cat_accesorios, _ = Categoria.objects.get_or_create(nombre='Accesorios')
        cat_accion, _     = Categoria.objects.get_or_create(nombre='Acción', defaults={'padre': cat_juegos})
        cat_rpg, _        = Categoria.objects.get_or_create(nombre='RPG', defaults={'padre': cat_juegos})
        cat_fps, _        = Categoria.objects.get_or_create(nombre='FPS', defaults={'padre': cat_juegos})

        # ── Plataformas ──
        plat_db = {}
        for nombre in ['PC', 'PlayStation 5', 'Xbox Series X', 'Nintendo Switch']:
            p, _ = Plataforma.objects.get_or_create(nombre=nombre)
            plat_db[nombre] = p

        # ════ CONSOLAS Y PERIFÉRICOS ════
        self.stdout.write(self.style.HTTP_INFO('Cargando consolas y periféricos...'))
        hw_creados = 0
        for item, cat in [(c, cat_consolas) for c in CONSOLAS] + \
                          [(p, cat_accesorios) for p in PERIFERICOS]:
            if Producto.objects.filter(nombre=item['nombre']).exists():
                continue
            prod = Producto.objects.create(
                nombre          = item['nombre'],
                descripcion     = item['descripcion'],
                categoria       = cat,
                precio          = Decimal(str(item['precio'])),
                precio_original = Decimal(str(item['precio_original'])) if item['precio_original'] else None,
                stock           = item['stock'],
                imagen_url      = item['imagen'],
                ventas          = item['ventas'],
                valoracion      = Decimal(str(round(random.uniform(4.0, 5.0), 1))),
                especificaciones = item['specs'],
            )
            for pn in item['plataformas']:
                prod.plataformas.add(plat_db[pn])
            hw_creados += 1
            self.stdout.write(f'  + {item["nombre"]}')

        # ════ JUEGOS DESDE RAWG ════
        if not opts['solo_hardware']:
            api_key = _api_key()
            if not api_key or api_key == 'tu_api_key_de_rawg':
                self.stdout.write(self.style.WARNING(
                    '\nRAWG_API_KEY no configurada — se omiten los juegos.\n'
                    'Obtén una key gratis en https://rawg.io/apidocs y agrégala al .env'))
            else:
                self.stdout.write(self.style.HTTP_INFO('\nImportando juegos desde RAWG API...'))
                genero_cat = {'action': cat_accion, 'role-playing-games-rpg': cat_rpg, 'shooter': cat_fps}
                url = 'https://api.rawg.io/api/games?' + urllib.parse.urlencode({
                    'key': api_key, 'page_size': min(opts['juegos'], 40), 'ordering': '-rating', 'exclude_tags': 'erotic,hentai,nsfw,sexual-content,nudity'})
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Monolith/1.0'})
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = json.loads(resp.read().decode())
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error API RAWG: {e}'))
                    data = {'results': []}

                juegos_creados = 0
                for juego in data.get('results', []):
                    nombre = juego.get('name', '').strip()
                    if not nombre or Producto.objects.filter(nombre=nombre).exists():
                        continue
                    if is_adult_game(juego):
                        self.stdout.write(self.style.WARNING(f'  - omitido por filtro adulto: {nombre}'))
                        continue
                    
                    # ── Filtrar por plataformas permitidas ──
                    plataformas_validas = []
                    for pinfo in juego.get('platforms', []):
                        ps = MAPEO_PLATAFORMAS.get(pinfo.get('platform', {}).get('slug', ''))
                        if ps and ps in CONSOLAS_PERMITIDAS:
                            plataformas_validas.append(ps)
                    
                    # Si no tiene ninguna plataforma válida, saltar este juego
                    if not plataformas_validas:
                        continue
                    
                    categoria = cat_juegos
                    for g in juego.get('genres', []):
                        if g.get('slug') in genero_cat:
                            categoria = genero_cat[g['slug']]; break
                    
                    rating = juego.get('rating', 3.5) or 3.5
                    precio = Decimal(str(round(80 + rating * 35, 2)))
                    
                    # ── Asegurar que siempre tenga precio (stock > 0) ──
                    stock = random.randint(5, 40)  # Mínimo 5 para asegurar disponibilidad
                    
                    desc = random.random() < 0.35
                    prod = Producto.objects.create(
                        nombre=nombre,
                        descripcion=f'{nombre} — disponible en Monolith Gaming Store.',
                        categoria=categoria, precio=precio,
                        precio_original=(precio*Decimal('1.25')).quantize(Decimal('0.01')) if desc else None,
                        stock=stock,
                        imagen_url=juego.get('background_image', '') or '',
                        ventas=juego.get('added', 0) or random.randint(0, 500),
                        valoracion=Decimal(str(round(rating, 1))),
                        especificaciones={
                            'Género': ', '.join(g['name'] for g in juego.get('genres', [])[:3]) or 'N/D',
                            'Lanzamiento': juego.get('released', 'N/D') or 'N/D',
                            'Rating': f'{rating}/5',
                            'Metacritic': str(juego.get('metacritic', 'N/D')),
                        },
                    )
                    
                    # Agregar solo plataformas permitidas
                    for pn in set(plataformas_validas):
                        prod.plataformas.add(plat_db[pn])
                    
                    juegos_creados += 1
                    self.stdout.write(f'  + {nombre} ({", ".join(plataformas_validas)})')
                self.stdout.write(self.style.SUCCESS(f'{juegos_creados} juegos importados desde RAWG'))

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Catálogo cargado. {hw_creados} consolas/periféricos. '
            f'Total productos: {Producto.objects.count()}'))
