"""Curated catalog artwork shared by every client; no database writes or name search."""
import json
from pathlib import Path


_COVERS = {entry['product_id']: entry for entry in json.loads(
    Path(__file__).with_name('covers.json').read_text(encoding='utf-8'))}


def catalog_cover(product):
    entry = _COVERS.get(product.pk)
    if entry is None:
        return None
    # Never override a different product or a subsequent administrator image edit.
    if (product.nombre != entry['name'] or product.slug != entry['slug']
            or product.imagen_url != entry['replaces_url']
            or str(product.imagen_principal or '') != entry['replaces_file']):
        return None
    return {'url': entry['url'], 'alt': entry['name'],
            'source_url': entry['source_url'], 'kind': entry['kind']}
