import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'
import {
  getTranslatedCategory,
  getTranslatedPlatform,
  getTranslatedSpec,
  getTranslatedText
} from '../i18n'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

function imageOf(product) {
  return product?.imagen_url || product?.imagen_principal || ''
}

function normalizeText(value) {
  return String(value ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export default function Cart({ t, user, onNavigate, onCartChange }) {
  const [cart, setCart] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)
  const [preview, setPreview] = useState(null)

  const [categories, setCategories] = useState([])
  const [platforms, setPlatforms] = useState([])

  const [cartSearch, setCartSearch] = useState('')
  const [cartTypeFilter, setCartTypeFilter] = useState('')
  const [cartPlatformFilter, setCartPlatformFilter] = useState('')
  const [cartSort, setCartSort] = useState('agregado')

  const [quickSearch, setQuickSearch] = useState('')
  const [quickCategory, setQuickCategory] = useState('')
  const [quickPlatform, setQuickPlatform] = useState('')
  const [quickSort, setQuickSort] = useState('-ventas')
  const [quickProducts, setQuickProducts] = useState([])
  const [quickLoading, setQuickLoading] = useState(false)

  const categoryOptions = useMemo(() => {
    const options = []

    ;(categories || []).forEach((cat) => {
      const childSlugs = (cat.subcategorias || []).map((sub) => sub.slug).filter(Boolean)

      options.push({
        slug: cat.slug,
        label: getTranslatedCategory(t, cat),
        slugs: [cat.slug, ...childSlugs].filter(Boolean),
        parent: true
      })

      ;(cat.subcategorias || []).forEach((sub) => {
        options.push({
          slug: sub.slug,
          label: `— ${getTranslatedCategory(t, sub)}`,
          slugs: [sub.slug].filter(Boolean),
          parent: false
        })
      })
    })

    return options
  }, [categories, t])

  const selectedCategorySlugs = useMemo(() => {
    if (!cartTypeFilter) return []

    const option = categoryOptions.find((item) => item.slug === cartTypeFilter)

    return option?.slugs || [cartTypeFilter]
  }, [cartTypeFilter, categoryOptions])

  const load = async () => {
    try {
      setError('')

      const { data } = await api.get('/cart/')

      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const loadFilters = async () => {
    try {
      const [catRes, platRes] = await Promise.all([
        api.get('/categorias/'),
        api.get('/plataformas/')
      ])

      setCategories(catRes.data.results || catRes.data || [])
      setPlatforms(platRes.data.results || platRes.data || [])
    } catch {
      setCategories([])
      setPlatforms([])
    }
  }

  const loadQuickProducts = async () => {
    try {
      setQuickLoading(true)

      const params = {
        page_size: 8,
        ordering: quickSort
      }

      if (quickSearch.trim().length >= 2) {
        params.search = quickSearch.trim()
      }

      if (quickCategory) {
        params.categoria = quickCategory
      }

      if (quickPlatform) {
        params.plataforma = quickPlatform
      }

      const { data } = await api.get('/productos/', { params })

      setQuickProducts(data.results || data || [])
    } catch {
      setQuickProducts([])
    } finally {
      setQuickLoading(false)
    }
  }

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    load()
    loadFilters()
  }, [user])

  useEffect(() => {
    if (!user) return

    const timer = window.setTimeout(loadQuickProducts, 250)

    return () => window.clearTimeout(timer)
  }, [user, quickSearch, quickCategory, quickPlatform, quickSort])

  const patch = async (id, accion) => {
    try {
      setError('')
      setNotice(null)

      const { data } = await api.patch(`/cart/items/${id}/`, { accion })

      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const remove = async (id) => {
    const ok = window.confirm(t.confirmRemoveCartItem)

    if (!ok) return

    try {
      setError('')
      setNotice(null)

      const { data } = await api.delete(`/cart/items/${id}/`)

      setCart(data)
      onCartChange?.()
      setNotice({ type: 'success', key: 'cartItemRemoved' })
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const clear = async () => {
    const ok = window.confirm(t.confirmClearCart)

    if (!ok) return

    try {
      setError('')
      setNotice(null)

      const { data } = await api.post('/cart/clear/')

      setCart(data)
      onCartChange?.()
      setNotice({ type: 'success', key: 'cartCleared' })
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const addProduct = async (productoId) => {
    try {
      setError('')
      setNotice(null)

      const { data } = await api.post('/cart/add/', {
        producto_id: productoId,
        cantidad: 1
      })

      setCart(data)
      onCartChange?.()
      setNotice({ type: 'success', key: 'addedToCart' })
      loadQuickProducts()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const checkout = async () => {
    try {
      setError('')
      setNotice(null)

      const { data } = await api.post('/cart/checkout/')

      setCart(data.carrito || data)
      onCartChange?.()
      setNotice({
        type: 'success',
        key: 'orderCreated',
        extra: data.pedido?.numero
      })
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const filteredItems = useMemo(() => {
    const search = normalizeText(cartSearch)

    return [...(cart?.items || [])]
      .filter((item) => {
        const product = item.producto || {}
        const categorySlug = product.categoria?.slug || ''
        const platformSlugs = (product.plataformas || []).map((platform) => platform.slug)

        if (selectedCategorySlugs.length > 0 && !selectedCategorySlugs.includes(categorySlug)) {
          return false
        }

        if (cartPlatformFilter && !platformSlugs.includes(cartPlatformFilter)) {
          return false
        }

        if (search.length >= 2) {
          const specText = Object.entries(product.especificaciones || {})
            .map(([key, value]) => `${key} ${value}`)
            .join(' ')

          const haystack = normalizeText([
            product.nombre,
            product.categoria?.nombre,
            ...(product.plataformas || []).map((platform) => platform.nombre),
            specText
          ].join(' '))

          if (!haystack.includes(search)) {
            return false
          }
        }

        return true
      })
      .sort((a, b) => {
        if (cartSort === 'precio_asc') {
          return toNumber(a.producto.precio) - toNumber(b.producto.precio)
        }

        if (cartSort === 'precio_desc') {
          return toNumber(b.producto.precio) - toNumber(a.producto.precio)
        }

        if (cartSort === 'popularidad') {
          return (b.producto.ventas || 0) - (a.producto.ventas || 0)
        }

        return new Date(b.agregado) - new Date(a.agregado)
      })
  }, [cart, cartSearch, selectedCategorySlugs, cartPlatformFilter, cartSort])

  const grouped = useMemo(() => {
    return filteredItems.reduce((groups, item) => {
      const key = getTranslatedCategory(t, item.producto?.categoria) || t.noCategory || 'Sin categoría'

      if (!groups[key]) {
        groups[key] = []
      }

      groups[key].push(item)

      return groups
    }, {})
  }, [filteredItems, t])

  if (error) {
    return (
      <div className="panel-page">
        <div className="alert error">{getTranslatedText(t, error)}</div>
      </div>
    )
  }

  if (!cart) {
    return <div className="loading-m">{t.loadingCart}</div>
  }

  return (
    <div className="panel-page">
      <div className="section-tag">{t.cartSprint}</div>
      <h1>{t.cart}</h1>

      {notice && (
        <div className={`alert ${notice.type === 'success' ? 'success' : 'warn'}`}>
          {t[notice.key] || getTranslatedText(t, notice.key)}
          {notice.extra ? ` ${notice.extra}` : ''}
        </div>
      )}

      {cart.mensajes?.map((message) => (
        <div className="alert warn" key={message}>
          {getTranslatedText(t, message)}
        </div>
      ))}

      <section className="panel-card cart-catalog-panel">
        <h2>{t.quickCatalogFromCart}</h2>

        <div className="cart-search-row">
          <div className="quick-search-cell">
            <input
              className="input-m"
              value={quickSearch}
              onChange={(event) => setQuickSearch(event.target.value)}
              placeholder={t.quickSearchPlaceholder}
            />

            {quickSearch.trim().length >= 2 && (
              <div className="steam-suggest cart-suggest">
                <div className="suggest-title">{t.suggestionsTitle}</div>

                {quickProducts.length > 0 ? (
                  quickProducts.slice(0, 5).map((product) => (
                    <button
                      key={product.id}
                      className="suggest-item"
                      type="button"
                      onClick={() => onNavigate('detail', { productId: product.id })}
                    >
                      <img src={imageOf(product)} alt={product.nombre} />

                      <span>
                        <strong>{product.nombre}</strong>
                        <em>S/ {toNumber(product.precio).toFixed(2)}</em>
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="suggest-empty">{t.noSuggestions}</div>
                )}
              </div>
            )}
          </div>

          <select
            className="input-m"
            value={quickPlatform}
            onChange={(event) => setQuickPlatform(event.target.value)}
          >
            <option value="">{t.allPlatforms}</option>

            {platforms.map((platform) => (
              <option key={platform.slug} value={platform.slug}>
                {getTranslatedPlatform(t, platform)}
              </option>
            ))}
          </select>

          <select
            className="input-m"
            value={quickCategory}
            onChange={(event) => setQuickCategory(event.target.value)}
          >
            <option value="">{t.allCategories}</option>

            {categoryOptions.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.label}
              </option>
            ))}
          </select>

          <select
            className="input-m"
            value={quickSort}
            onChange={(event) => setQuickSort(event.target.value)}
          >
            <option value="-ventas">{t.popularity}</option>
            <option value="precio">{t.priceAsc}</option>
            <option value="-precio">{t.priceDesc}</option>
            <option value="nombre">{t.nameAsc}</option>
          </select>

          <button className="btn-ghost" type="button" onClick={loadQuickProducts}>
            {quickLoading ? t.loading || '...' : t.search}
          </button>
        </div>

        <div className="mini-products-grid quick-catalog-grid">
          {quickProducts.map((product) => (
            <div className="mini-prod" key={product.id}>
              <img
                src={imageOf(product)}
                alt={product.nombre}
                onClick={() => setPreview(imageOf(product))}
              />

              <div className="mini-prod-info">
                <button
                  className="link-reset prod-name"
                  onClick={() => onNavigate('detail', { productId: product.id })}
                >
                  {product.nombre}
                </button>

                <div className="muted">
                  S/ {toNumber(product.precio).toFixed(2)} · {t.stock}: {product.stock}
                </div>

                {product.cantidad_en_carrito > 0 && (
                  <div className="muted">
                    {t.alreadyHave}: {product.cantidad_en_carrito}
                  </div>
                )}
              </div>

              <button
                className="btn-outline-neon"
                type="button"
                disabled={!product.disponible}
                onClick={() => addProduct(product.id)}
              >
                {t.addCart}
              </button>
            </div>
          ))}
        </div>
      </section>

      {cart.vacio ? (
        <div className="empty-state">
          <h3>{t.emptyCart}</h3>
          <p>{t.emptyCartMessage}</p>

          <button className="btn-neon" onClick={() => onNavigate('catalog')}>
            {t.goToCatalog}
          </button>
        </div>
      ) : (
        <>
          <div className="cart-toolbar cart-toolbar-full">
            <input
              className="input-m"
              value={cartSearch}
              onChange={(event) => setCartSearch(event.target.value)}
              placeholder={t.searchCartPlaceholder}
            />

            <select
              className="input-m"
              value={cartTypeFilter}
              onChange={(event) => setCartTypeFilter(event.target.value)}
            >
              <option value="">{t.allTypes}</option>

              {categoryOptions.map((category) => (
                <option key={category.slug} value={category.slug}>
                  {category.label}
                </option>
              ))}
            </select>

            <select
              className="input-m"
              value={cartPlatformFilter}
              onChange={(event) => setCartPlatformFilter(event.target.value)}
            >
              <option value="">{t.allPlatforms}</option>

              {platforms.map((platform) => (
                <option key={platform.slug} value={platform.slug}>
                  {getTranslatedPlatform(t, platform)}
                </option>
              ))}
            </select>

            <select
              className="input-m"
              value={cartSort}
              onChange={(event) => setCartSort(event.target.value)}
            >
              <option value="agregado">{t.recentlyAdded}</option>
              <option value="precio_asc">{t.priceAsc}</option>
              <option value="precio_desc">{t.priceDesc}</option>
              <option value="popularidad">{t.popularity}</option>
            </select>
          </div>

          {filteredItems.length === 0 ? (
            <div className="empty-state small">
              <h3>{t.noCartMatches}</h3>

              <button
                className="btn-ghost"
                onClick={() => {
                  setCartSearch('')
                  setCartTypeFilter('')
                  setCartPlatformFilter('')
                }}
              >
                {t.clear}
              </button>
            </div>
          ) : (
            Object.entries(grouped).map(([group, items]) => (
              <section className="cart-group" key={group}>
                <h2>{group}</h2>

                <div className="cart-list">
                  {items.map((item) => (
                    <div className="cart-item" key={item.id}>
                      <img
                        src={imageOf(item.producto)}
                        alt={item.producto.nombre}
                        onClick={() => setPreview(imageOf(item.producto))}
                      />

                      <div>
                        <button
                          className="link-reset prod-name"
                          onClick={() => onNavigate('detail', { productId: item.producto.id })}
                        >
                          {item.producto.nombre}
                        </button>

                        <div className="muted">
                          {t.currentPrice} S/ {toNumber(item.producto.precio).toFixed(2)} · {t.subtotal} S/ {toNumber(item.subtotal).toFixed(2)}
                        </div>

                        <div className="muted">
                          {t.stockAvailable}: {item.producto.stock} · {t.inCart}: {item.cantidad}
                        </div>

                        <div className="muted">
                          {item.producto.plataformas?.map((platform) => getTranslatedPlatform(t, platform)).join(', ')}
                        </div>

                        {item.precio_cambio && (
                          <span className="badge-warn">{t.priceChanged}</span>
                        )}

                        {item.stock_insuficiente && (
                          <span className="badge-warn">{t.insufficientStock}</span>
                        )}

                        <div className="spec-list">
                          {Object.entries(item.producto.especificaciones || {}).slice(0, 3).map(([key, value]) => (
                            <span key={key}>
                              {getTranslatedSpec(t, key)}: {value}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="qty">
                        <button onClick={() => patch(item.id, 'menos')}>−</button>
                        <span>{item.cantidad}</span>
                        <button
                          onClick={() => patch(item.id, 'mas')}
                          disabled={item.cantidad >= item.producto.stock}
                        >
                          +
                        </button>
                      </div>

                      <button className="btn-ghost" onClick={() => remove(item.id)}>
                        {t.delete}
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            ))
          )}

          {cart.compatibilidad && (
            <div className={`alert ${cart.compatibilidad.ok ? 'success' : 'warn'}`}>
              {t.compatibility}: {getTranslatedText(t, cart.compatibilidad.mensaje)}
              {cart.compatibilidad.plataformas_comunes?.length > 0 &&
                ` ${t.commonPlatform}: ${cart.compatibilidad.plataformas_comunes.join(', ')}`}
            </div>
          )}

          {(cart.recomendados?.length > 0 || cart.accesorios?.length > 0) && (
            <section className="panel-card">
              <h2>{t.suggestions}</h2>

              <div className="mini-products-grid">
                {[...(cart.recomendados || []), ...(cart.accesorios || [])].slice(0, 8).map((product) => (
                  <div className="mini-prod" key={`${product.id}-${product.nombre}`}>
                    <img
                      src={imageOf(product)}
                      alt={product.nombre}
                      onClick={() => setPreview(imageOf(product))}
                    />

                    <div className="mini-prod-info">
                      <button
                        className="link-reset prod-name"
                        onClick={() => onNavigate('detail', { productId: product.id })}
                      >
                        {product.nombre}
                      </button>

                      <div className="muted">
                        S/ {toNumber(product.precio).toFixed(2)}
                      </div>
                    </div>

                    <button className="btn-outline-neon" onClick={() => addProduct(product.id)}>
                      {t.addCart}
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="cart-total">
            <span>{t.total}</span>
            <strong>S/ {toNumber(cart.total).toFixed(2)}</strong>
          </div>

          <div className="row-actions">
            <button className="btn-ghost" onClick={clear}>
              {t.empty}
            </button>

            <button
              className="btn-neon"
              onClick={checkout}
              disabled={cart.vacio || (cart.items || []).some((item) => item.stock_insuficiente)}
            >
              {t.confirmOrder}
            </button>
          </div>
        </>
      )}

      {preview && (
        <div className="image-modal" onClick={() => setPreview(null)}>
          <img src={preview} alt={t.imagePreview} />
          <button className="btn-ghost">{t.close}</button>
        </div>
      )}
    </div>
  )
}