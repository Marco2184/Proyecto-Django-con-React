import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'

export default function Cart({ t, user, onNavigate, onCartChange }) {
  const [cart, setCart] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [categorias, setCategorias] = useState([])
  const [cartTypeFilter, setCartTypeFilter] = useState('')
  const [cartSort, setCartSort] = useState('agregado')
  const [preview, setPreview] = useState(null)

  const load = async () => {
    try {
      const { data } = await api.get('/cart/')
      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const loadCategories = async () => {
    try {
      const { data } = await api.get('/categorias/')
      setCategorias(data.results || data)
    } catch {
      setCategorias([])
    }
  }

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    load()
    loadCategories()
  }, [user])

  const patch = async (id, accion) => {
    try {
      const { data } = await api.patch(`/cart/items/${id}/`, { accion })
      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const remove = async (id) => {
    try {
      const { data } = await api.delete(`/cart/items/${id}/`)
      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const clear = async () => {
    try {
      const { data } = await api.post('/cart/clear/')
      setCart(data)
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const grouped = useMemo(() => {
    const groups = {}

    const sorted = [...(cart?.items || [])].sort((a, b) => {
      if (cartSort === 'precio_asc') {
        return parseFloat(a.producto.precio) - parseFloat(b.producto.precio)
      }

      if (cartSort === 'precio_desc') {
        return parseFloat(b.producto.precio) - parseFloat(a.producto.precio)
      }

      if (cartSort === 'popularidad') {
        return (b.producto.ventas || 0) - (a.producto.ventas || 0)
      }

      return new Date(b.agregado) - new Date(a.agregado)
    })

    sorted.forEach((item) => {
      const categoryName = item.producto.categoria?.nombre || 'Sin categoría'

      if (cartTypeFilter && item.producto.categoria?.slug !== cartTypeFilter) {
        return
      }

      if (!groups[categoryName]) {
        groups[categoryName] = []
      }

      groups[categoryName].push(item)
    })

    return groups
  }, [cart, cartTypeFilter, cartSort])

  if (error) {
    return (
      <div className="panel-page">
        <div className="alert error">{error}</div>
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

      {msg && <div className="alert success">{msg}</div>}

      {cart.mensajes?.map((message) => (
        <div className="alert" key={message}>
          {message}
        </div>
      ))}

      {cart.vacio ? (
        <div className="empty-state">
          <h3>{t.emptyCart}</h3>
          <p>{t.emptyCartMessage || 'No tienes productos agregados todavía.'}</p>
          <button className="btn-neon" onClick={() => onNavigate('catalog')}>
            {t.goToCatalog}
          </button>
        </div>
      ) : (
        <>
          <div className="cart-toolbar">
            <span className="muted">{t.groupFilterSort}</span>

            <select
              className="input-m"
              value={cartTypeFilter}
              onChange={(event) => setCartTypeFilter(event.target.value)}
            >
              <option value="">{t.allTypes}</option>
              {categorias.map((categoria) => (
                <option key={categoria.slug} value={categoria.slug}>
                  {categoria.nombre}
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

          {Object.entries(grouped).map(([group, items]) => (
            <section className="cart-group" key={group}>
              <h2>{group}</h2>

              <div className="cart-list">
                {items.map((item) => (
                  <div className="cart-item" key={item.id}>
                    <img
                      src={item.producto.imagen_url || item.producto.imagen_principal}
                      alt={item.producto.nombre}
                      onClick={() =>
                        setPreview(item.producto.imagen_url || item.producto.imagen_principal)
                      }
                    />

                    <div>
                      <button
                        className="link-reset prod-name"
                        onClick={() =>
                          onNavigate('detail', { productId: item.producto.id })
                        }
                      >
                        {item.producto.nombre}
                      </button>

                      <div className="muted">
                        {t.currentPrice} S/ {parseFloat(item.producto.precio).toFixed(2)} ·{' '}
                        {t.subtotal} S/ {parseFloat(item.subtotal).toFixed(2)}
                      </div>

                      <div className="muted">
                        {t.stockAvailable}: {item.producto.stock}
                      </div>

                      {item.precio_cambio && (
                        <span className="badge-warn">{t.priceChanged}</span>
                      )}

                      {item.stock_insuficiente && (
                        <span className="badge-warn">{t.insufficientStock}</span>
                      )}

                      <div className="spec-list">
                        {Object.entries(item.producto.especificaciones || {})
                          .slice(0, 3)
                          .map(([key, value]) => (
                            <span key={key}>
                              {key}: {value}
                            </span>
                          ))}
                      </div>
                    </div>

                    <div className="qty">
                      <button onClick={() => patch(item.id, 'menos')}>−</button>
                      <span>{item.cantidad}</span>
                      <button onClick={() => patch(item.id, 'mas')}>+</button>
                    </div>

                    <button className="btn-ghost" onClick={() => remove(item.id)}>
                      {t.delete}
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ))}

          {cart.compatibilidad && (
            <div className={`alert ${cart.compatibilidad.ok ? 'success' : 'warn'}`}>
              {t.compatibility}: {cart.compatibilidad.mensaje}
              {cart.compatibilidad.plataformas_comunes?.length > 0 &&
                ` ${t.commonPlatform}: ${cart.compatibilidad.plataformas_comunes.join(', ')}`}
            </div>
          )}

          <div className="cart-total">
            <span>{t.total}</span>
            <strong>S/ {parseFloat(cart.total).toFixed(2)}</strong>
          </div>

          <div className="row-actions">
            <button className="btn-ghost" onClick={clear}>
              {t.empty}
            </button>

            <button className="btn-neon">
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