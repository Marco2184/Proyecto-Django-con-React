import covers from './covers.json' with {type: 'json'}

const byId = new Map(covers.map(cover => [cover.product_id, cover]))

function legacyCover(product) {
  const cover = byId.get(product?.id)
  if (!cover || product.nombre !== cover.name || product.slug !== cover.slug ||
      product.imagen_url !== cover.replaces_url) return null
  const file = product.imagen_principal || ''
  if (file === cover.replaces_file) return cover
  // DRF can return an absolute URL or a /media/ path for the same uploaded file.
  try {
    return new URL(file, 'https://monolith.invalid').pathname === `/media/${cover.replaces_file}` ? cover : null
  } catch {
    return null
  }
}

// An explicit empty cover must not fall back to an unrelated legacy image.
export function imageOf(product) {
  const cover = legacyCover(product)
  if (cover?.url.startsWith('/covers/')) return cover.url
  if (product?.portada) return product.portada.url || ''
  if (cover) return cover.url
  return product?.imagen_url || product?.imagen_principal || ''
}
