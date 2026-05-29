"""
Importa productos gaming desde la API pública de RAWG (https://rawg.io/apidocs).
Mantiene las categorías existentes: Juegos, Consolas, Accesorios y sus subcategorías.

Uso:
    python manage.py importar_productos
    python manage.py importar_productos --cantidad 40

Requiere una API key gratuita de https://rawg.io/apidocs
Configúrala en el archivo .env:  RAWG_API_KEY=tu_key
"""
import random
import urllib.request
import urllib.parse
import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from productos.models import Producto, Categoria, Plataforma


def _get_api_key():
    """Lee RAWG_API_KEY del .env o variables de entorno."""
    from pathlib import Path
    import os
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


# Mapeo de plataformas RAWG → plataformas locales
MAPEO_PLATAFORMAS = {
    'pc':               'PC',
    'playstation5':     'PlayStation 5',
    'playstation4':     'PlayStation 5',
    'xbox-series-x':    'Xbox Series X',
    'xbox-one':         'Xbox Series X',
    'nintendo-switch':  'Nintendo Switch',
}


class Command(BaseCommand):
    help = 'Importa juegos desde la API de RAWG manteniendo las categorías existentes'

    def add_arguments(self, parser):
        parser.add_argument('--cantidad', type=int, default=20,
                            help='Cantidad de juegos a importar (default 20)')

    def handle(self, *args, **opts):
        api_key = _get_api_key()
        if not api_key:
            self.stdout.write(self.style.ERROR(
                'Falta RAWG_API_KEY. Obtén una gratis en https://rawg.io/apidocs '
                'y agrégala al archivo .env como RAWG_API_KEY=tu_key'))
            return

        cantidad = opts['cantidad']
        page_size = min(cantidad, 40)

        # ── Asegurar categorías base (NO se modifican si ya existen) ──
        cat_juegos, _    = Categoria.objects.get_or_create(nombre='Juegos')
        cat_accion, _    = Categoria.objects.get_or_create(nombre='Acción', defaults={'padre': cat_juegos})
        cat_rpg, _       = Categoria.objects.get_or_create(nombre='RPG', defaults={'padre': cat_juegos})
        cat_fps, _       = Categoria.objects.get_or_create(nombre='FPS', defaults={'padre': cat_juegos})

        # Mapeo de géneros RAWG → subcategorías locales
        genero_a_cat = {
            'action':            cat_accion,
            'role-playing-games-rpg': cat_rpg,
            'shooter':           cat_fps,
        }

        # ── Llamada a la API ──
        url = 'https://api.rawg.io/api/games?' + urllib.parse.urlencode({
            'key':       api_key,
            'page_size': page_size,
            'ordering':  '-rating',
            'exclude_tags': 'erotic,hentai,nsfw,sexual-content,nudity,adult,adult-only',
        })

        self.stdout.write(f'Consultando RAWG API ({page_size} juegos)...')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Monolith/1.0'})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al consultar la API: {e}'))
            return

        # ── Plataformas locales ──
        plataformas_db = {}
        for slug, nombre in set(MAPEO_PLATAFORMAS.items()):
            p, _ = Plataforma.objects.get_or_create(nombre=nombre)
            plataformas_db[nombre] = p

        creados = 0
        for juego in data.get('results', []):
            nombre = juego.get('name', '').strip()
            if not nombre or Producto.objects.filter(nombre=nombre).exists():
                continue
            if is_adult_game(juego):
                self.stdout.write(self.style.WARNING(f'  - omitido por filtro adulto: {nombre}'))
                continue

            # Categoría según primer género
            categoria = cat_juegos
            for g in juego.get('genres', []):
                if g.get('slug') in genero_a_cat:
                    categoria = genero_a_cat[g['slug']]
                    break

            # Precio simulado según rating
            rating = juego.get('rating', 3.5) or 3.5
            precio = Decimal(str(round(80 + rating * 35, 2)))
            con_descuento = random.random() < 0.35
            precio_original = (precio * Decimal('1.25')).quantize(Decimal('0.01')) if con_descuento else None

            producto = Producto.objects.create(
                nombre          = nombre,
                descripcion     = f"{nombre} — disponible en Monolith Gaming Store.",
                categoria       = categoria,
                precio          = precio,
                precio_original = precio_original,
                stock           = random.randint(0, 40),
                imagen_url      = juego.get('background_image', '') or '',
                ventas          = juego.get('added', 0) or random.randint(0, 500),
                valoracion      = Decimal(str(round(rating, 1))),
                especificaciones = {
                    'Género':       ', '.join(g['name'] for g in juego.get('genres', [])[:3]) or 'N/D',
                    'Lanzamiento':  juego.get('released', 'N/D') or 'N/D',
                    'Rating':       f"{rating}/5",
                    'Metacritic':   str(juego.get('metacritic', 'N/D')),
                },
            )

            # Plataformas
            for pinfo in juego.get('platforms', []):
                pslug = pinfo.get('platform', {}).get('slug', '')
                if pslug := MAPEO_PLATAFORMAS.get(pslug):
                    producto.plataformas.add(plataformas_db[pslug])

            creados += 1
            self.stdout.write(f'  + {nombre}')

        self.stdout.write(self.style.SUCCESS(
            f'\n{creados} productos importados desde RAWG. '
            f'Total en catálogo: {Producto.objects.count()}'))
