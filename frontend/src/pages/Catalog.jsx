import { useState, useEffect, useRef } from 'react'
import { api, getApiError } from '../services/api'
import { getTranslatedCategory, getTranslatedPlatform } from '../i18n'

export default function Catalog({ t, onNavigate, user, onCartChange }) {
  const [productos, setProductos] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [suggestOpen, setSuggestOpen] = useState(false)
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [sort, setSort] = useState('popularidad')
  const [plataformas, setPlataformas] = useState([])
  const [categorias, setCategorias] = useState([])
  const [platSel, setPlatSel] = useState([])
  const [catSel, setCatSel] = useState('')
  const [total, setTotal] = useState(0)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const searchBoxRef = useRef(null)

  useEffect(() => {
    fetchMeta()
    fetchProductos('')
  }, [])

  useEffect(() => {
    fetchProductos(search)
  }, [sort, platSel, catSel])

  useEffect(() => {
    const timer = setInterval(() => fetchProductos(search), 30000)

    const onFocus = () => fetchProductos(search)

    window.addEventListener('focus', onFocus)

    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [search, sort, platSel, catSel])

  useEffect(() => {
    const q = search.trim()

    if (q.length < 2) {
      setSuggestions([])
      setSuggestOpen(false)
      return
    }

    const timer = setTimeout(async () => {
      setSuggestLoading(true)

      try {
        const { data } = await api.get(
          `/productos/buscar/?q=${encodeURIComponent(q)}`
        )

        setSuggestions(data.resultados || [])
        setSuggestOpen(true)
      } catch {
        setSuggestions([])
      } finally {
        setSuggestLoading(false)
      }
    }, 180)

    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    const closeSuggestions = (event) => {
      if (
        searchBoxRef.current &&
        !searchBoxRef.current.contains(event.target)
      ) {
        setSuggestOpen(false)
      }
    }

    document.addEventListener('mousedown', closeSuggestions)

    return () => document.removeEventListener('mousedown', closeSuggestions)
  }, [])

  const fetchMeta = async () => {
    try {
      const [platformResponse, categoryResponse] = await Promise.all([
        api.get('/plataformas/'),
        api.get('/categorias/')
      ])

      setPlataformas(platformResponse.data.results || platformResponse.data)
      setCategorias(categoryResponse.data.results || categoryResponse.data)
    } catch (error) {
      console.error(error)
    }
  }

  const buildParams = (q = search) => {
    const params = new URLSearchParams()
    const trimmed = q.trim()

    if (trimmed.length >= 2) {
      params.set('search', trimmed)
    }

    if (sort === 'precio_asc') {
      params.set('ordering', 'precio')
    } else if (sort === 'precio_desc') {
      params.set('ordering', '-precio')
    } else if (sort === 'recientes') {
      params.set('ordering', '-activo')
    } else {
      params.set('ordering', '-ventas')
    }

    platSel.forEach((platformSlug) => {
      params.append('plataforma', platformSlug)
    })

    if (catSel) {
      params.set('categoria', catSel)
    }

    return params.toString()
  }

  const fetchProductos = async (q = search) => {
    setLoading(true)
    setError('')

    try {
      const { data } = await api.get(`/productos/?${buildParams(q)}`)
      const list = data.results || data

      setProductos(list)
      setTotal(data.count ?? list.length)
    } catch (err) {
      setError(getApiError(err))
      setProductos([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setSuggestOpen(false)
    fetchProductos(search)
  }

  const clearSearch = () => {
    setSearch('')
    setSuggestions([])
    setSuggestOpen(false)
    fetchProductos('')
  }

  const togglePlat = (slug) => {
    setPlatSel((prev) =>
      prev.includes(slug)
        ? prev.filter((platformSlug) => platformSlug !== slug)
        : [...prev, slug]
    )
  }

  const openProduct = (id) => {
    setSuggestOpen(false)
    onNavigate('detail', { productId: id })
  }

  const addToCart = async (productoId) => {
    if (!user) {
      return onNavigate('login')
    }

    setMsg('')
    setError('')

    try {
      await api.post('/cart/add/', {
        producto_id: productoId,
        cantidad: 1
      })

      setMsg(t.addedToCart)
      await fetchProductos(search)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  return (
    <div className="catalog-layout">
      <aside className="catalog-sidebar">
        <div className="section-tag" style={{ marginBottom: '1.25rem' }}>
          {t.filters}
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <div className="filter-title">{t.platform}</div>

          {plataformas.map((platform) => (
            <label
              key={platform.slug}
              className={`filter-label ${
                platSel.includes(platform.slug) ? 'active-filter' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={platSel.includes(platform.slug)}
                onChange={() => togglePlat(platform.slug)}
              />

              {getTranslatedPlatform(t, platform)}
            </label>
          ))}
        </div>

        <div>
          <div className="filter-title">{t.category}</div>

          <label className={`filter-label ${!catSel ? 'active-filter' : ''}`}>
            <input
              type="radio"
              name="cat"
              checked={!catSel}
              onChange={() => setCatSel('')}
            />

            {t.all}
          </label>

          {categorias.map((category) => (
            <div key={category.slug} className="cat-block">
              <label
                className={`filter-label ${
                  catSel === category.slug ? 'active-filter' : ''
                }`}
              >
                <input
                  type="radio"
                  name="cat"
                  checked={catSel === category.slug}
                  onChange={() => setCatSel(category.slug)}
                />

                {getTranslatedCategory(t, category)}
              </label>

              {(category.subcategorias || []).map((subcategory) => (
                <label
                  key={subcategory.slug}
                  className={`filter-label sub-filter ${
                    catSel === subcategory.slug ? 'active-filter' : ''
                  }`}
                >
                  <input
                    type="radio"
                    name="cat"
                    checked={catSel === subcategory.slug}
                    onChange={() => setCatSel(subcategory.slug)}
                  />

                  {getTranslatedCategory(t, subcategory)}
                </label>
              ))}
            </div>
          ))}
        </div>
      </aside>

      <main className="catalog-main">
        <div className="catalog-header">
          <div>
            <div className="section-tag">{t.productsCatalog}</div>
            <h1>{t.catalog}</h1>
            <div className="muted">
              {total} {t.found}
            </div>
          </div>

          <div className="sort-row">
            <span>{t.sort}</span>

            <select
              className="catalog-sort"
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="popularidad">{t.popular}</option>
              <option value="precio_asc">{t.priceAsc}</option>
              <option value="precio_desc">{t.priceDesc}</option>
              <option value="recientes">{t.recent}</option>
            </select>
          </div>
        </div>

        <div className="search-bar-wrap" ref={searchBoxRef}>
          <div className="search-row">
            <div className="search-input-wrap">
              <span className="search-icon">⌕</span>

              <input
                className="search-input-m"
                placeholder={t.searchPlaceholder}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onFocus={() =>
                  search.trim().length >= 2 && setSuggestOpen(true)
                }
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    handleSearch()
                  }
                }}
              />

              {suggestOpen && (
                <div className="steam-suggest">
                  <div className="suggest-title">{t.suggestionsTitle}</div>

                  {suggestLoading && (
                    <div className="suggest-empty">...</div>
                  )}

                  {!suggestLoading && suggestions.length === 0 && (
                    <div className="suggest-empty">{t.noSuggestions}</div>
                  )}

                  {suggestions.map((product) => (
                    <button
                      key={product.id}
                      className="suggest-item"
                      onMouseDown={(event) => {
                        event.preventDefault()
                        openProduct(product.id)
                      }}
                    >
                      <img
                        src={product.imagen_url || product.imagen_principal}
                        alt={product.nombre}
                      />

                      <span>
                        <strong>{product.nombre}</strong>
                        <em>S/ {parseFloat(product.precio).toFixed(2)}</em>
                      </span>
                    </button>
                  ))}

                  {suggestions.length > 0 && (
                    <>
                      <div className="suggest-title explore">
                        {t.exploreBy}
                      </div>

                      <button
                        className="suggest-chip"
                        onMouseDown={(event) => {
                          event.preventDefault()
                          handleSearch()
                        }}
                      >
                        {t.search}: “{search.trim()}”
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>

            <button className="btn-neon" onClick={handleSearch}>
              {t.search}
            </button>

            {search && (
              <button className="btn-ghost" onClick={clearSearch}>
                ✕ {t.clear}
              </button>
            )}
          </div>
        </div>

        {msg && <div className="alert success">{msg}</div>}
        {error && <div className="alert error">{error}</div>}

        {loading ? (
          <div className="loading-m">{t.loadingCatalog}</div>
        ) : productos.length === 0 ? (
          <div className="empty-state">
            <h4>{t.noResults}</h4>

            <button className="btn-outline-neon" onClick={clearSearch}>
              {t.seeAll}
            </button>
          </div>
        ) : (
          <div className="products-grid">
            {productos.map((product) => (
              <div key={product.id} className="prod-card">
                <div
                  className="prod-img"
                  onClick={() =>
                    onNavigate('detail', { productId: product.id })
                  }
                >
                  {product.imagen_url || product.imagen_principal ? (
                    <img
                      src={product.imagen_url || product.imagen_principal}
                      alt={product.nombre}
                    />
                  ) : (
                    <span className="prod-img-placeholder">MONOLITH</span>
                  )}
                </div>

                <div className="prod-body">
                  <div className="prod-badges">
                    {(product.plataformas || [])
                      .slice(0, 2)
                      .map((platform) => (
                        <span
                          key={platform.slug || platform.id}
                          className="badge-plat"
                        >
                          {getTranslatedPlatform(t, platform)}
                        </span>
                      ))}

                    {product.cantidad_en_carrito > 0 && (
                      <span className="badge-cart">
                        {t.inCart}: {product.cantidad_en_carrito}
                      </span>
                    )}

                    {product.tiene_descuento && (
                      <span className="prod-discount">
                        -{product.porcentaje_descuento}%
                      </span>
                    )}
                  </div>

                  <button
                    className="prod-name link-reset"
                    onClick={() =>
                      onNavigate('detail', { productId: product.id })
                    }
                  >
                    {product.nombre}
                  </button>

                  <div className="prod-price">
                    S/ {parseFloat(product.precio).toFixed(2)}

                    {product.tiene_descuento && (
                      <span className="prod-price-orig">
                        S/ {parseFloat(product.precio_original).toFixed(2)}
                      </span>
                    )}
                  </div>

                  <div
                    className={`prod-stock ${
                      product.disponible ? 'in-stock' : 'out-stock'
                    }`}
                  >
                    <span className="stock-dot" />

                    {product.disponible
                      ? `${t.available} (${product.stock})`
                      : t.outStock}
                  </div>

                  <button
                    className="btn-outline-neon card-btn"
                    onClick={() => addToCart(product.id)}
                    disabled={!product.disponible}
                  >
                    {t.addCart}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}