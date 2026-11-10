"""Artwork selection tests use unsaved products and never need a database."""
import json
from pathlib import Path
from django.test import SimpleTestCase
from productos.covers import catalog_cover
from productos.models import Producto
from productos.serializers import ProductoListSerializer


class CatalogCoverTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.entries = json.loads((Path(__file__).resolve().parents[1] /
                                  'productos/covers.json').read_text(encoding='utf-8'))

    def product(self, entry):
        return Producto(pk=entry['product_id'], nombre=entry['name'], slug=entry['slug'],
                        imagen_url=entry['replaces_url'], imagen_principal=entry['replaces_file'],
                        precio='100.00', stock=7)

    def test_every_catalog_entry_resolves_without_queries_or_mutating_product(self):
        serializer = ProductoListSerializer()
        for entry in self.entries:
            with self.subTest(product=entry['product_id']):
                product = self.product(entry)
                before = product.__dict__.copy()
                cover = catalog_cover(product)
                self.assertEqual(cover['url'], entry['url'])
                self.assertEqual(product.imagen, entry['url'])
                self.assertEqual(serializer.fields['imagen_url'].to_representation(product), entry['url'])
                self.assertEqual(serializer.fields['portada'].to_representation(product), cover)
                self.assertEqual(product.__dict__, before)

    def test_changed_identity_or_manual_image_edit_is_never_overridden(self):
        entry = next(e for e in self.entries if e['product_id'] == 25)
        for field, value in [('pk', 9999), ('nombre', 'The Last of Us Part I'),
                             ('slug', 'the-last-of-us-part-i'),
                             ('imagen_url', 'https://example.invalid/new-cover.jpg'),
                             ('imagen_principal', 'productos/manual.jpg')]:
            with self.subTest(field=field):
                product = self.product(entry)
                setattr(product, field, value)
                self.assertIsNone(catalog_cover(product))

    def test_remastered_and_part_i_and_witcher_expansions_have_distinct_artwork(self):
        entries = {e['product_id']: e for e in self.entries}
        for ids in [(25, 26), (14, 15, 16)]:
            self.assertEqual(len({entries[i]['url'] for i in ids}), len(ids))

    def test_local_cover_uses_catalog_artwork(self):
        entry = next(e for e in self.entries if e['product_id'] == 11)
        product = self.product(entry)
        self.assertEqual(entry['url'], '/covers/the-elder-scrolls-vi.jpg')
        self.assertEqual(product.imagen, entry['url'])
        self.assertEqual(catalog_cover(product)['url'], entry['url'])
        self.assertNotIn('unsplash', product.imagen)

    def test_unlisted_products_keep_their_current_images(self):
        product = Producto(pk=1, nombre='Console', slug='console', imagen_url='https://example.invalid/console.jpg')
        self.assertIsNone(catalog_cover(product))
        self.assertEqual(product.imagen, product.imagen_url)
        self.assertEqual(ProductoListSerializer().get_imagen_url(product), product.imagen_url)

    def test_manifest_has_unique_ids_and_explicit_https_sources(self):
        self.assertEqual(len(self.entries), 20)
        self.assertEqual(len({e['product_id'] for e in self.entries}), 20)
        self.assertEqual(sum(bool(e['url']) for e in self.entries), 20)
        for entry in self.entries:
            self.assertTrue(entry['source_url'].startswith('https://'))
            if entry['url']:
                self.assertTrue(
                        entry['url'].startswith('https://') or
                        entry['url'].startswith('/covers/')
                    )
                self.assertNotIn('..', entry['url'])
                self.assertNotIn('unsplash', entry['url'])
