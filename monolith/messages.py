from django.utils.translation import get_language


def message(es, en):
    """Bilingual API messages without depending on a deployment's gettext binary."""
    return en if (get_language() or 'es').startswith('en') else es
