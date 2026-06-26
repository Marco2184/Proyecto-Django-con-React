import { useEffect, useState } from 'react'
import { api, getApiError } from '../services/api'
import { getTranslatedPlatform, getTranslatedSpec, getTranslatedText } from '../i18n'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

function imageOf(product) {
  return product?.imagen_url || product?.imagen_principal || ''
}

export default function Cart({ t, user, onNavigate, onCartChange }) {
  const [cart, setCart] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)
  const [preview, setPreview] = useState(null)
  const [couponCode, setCouponCode] = useState('')
  const [couponLoading, setCouponLoading] = useState(false)
  const [couponError, setCouponError] = useState('')

  const load = async () => {
    try {
      setError('')

      const { data } = await api.get('/cart/')

      setCart(data)
      setCouponCode(data.cupon || '')
      onCartChange?.()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    load()
  }, [user])

  const patch = async (id, accion) => {
    try {
      setError('')
      setNotice(null)

      const { data } = await api.patch(`/cart/items/${id}/`, { accion })

      setCart(data)
      setCouponCode(data.cupon || '')
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
      setCouponCode(data.cupon || '')
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
      setCouponError('')

      const { data } = await api.post('/cart/clear/')

      setCart(data)
      setCouponCode('')
      onCartChange?.()
      setNotice({ type: 'success', key: 'cartCleared' })
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const applyCoupon = async () => {
    try {
      setCouponLoading(true)
      setCouponError('')
      setNotice(null)

      const { data } = await api.post('/cart/aplicar-cupon/', {
        codigo: couponCode.trim()
      })

      setCart(data)
      setCouponCode(data.cupon || couponCode.trim().toUpperCase())
      setNotice({ type: 'success', key: 'couponApplied', extra: data.cupon || couponCode.trim().toUpperCase() })
    } catch (err) {
      setCouponError(getApiError(err))
    } finally {
      setCouponLoading(false)
    }
  }

  const removeCoupon = async () => {
    try {
      setCouponLoading(true)
      setCouponError('')
      setNotice(null)

      const { data } = await api.post('/cart/quitar-cupon/')

      setCart(data)
      setCouponCode('')
      setNotice({ type: 'success', key: 'couponRemoved' })
    } catch (err) {
      setCouponError(getApiError(err))
    } finally {
      setCouponLoading(false)
    }
  }

  const checkout = () => {
    onNavigate('checkout')
  }

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
          <div className="cart-list">
            {(cart.items || []).map((item) => (
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

          <section className="panel-card cart-coupon-panel">
            <h2>{t.discountCode || 'Código de descuento'}</h2>

            <div className="cart-coupon-row">
              <input
                className="input-m"
                value={couponCode}
                onChange={(event) => setCouponCode(event.target.value.toUpperCase())}
                placeholder={t.discountCodePlaceholder || 'MONOLITH10, GAMER20 o NEON50'}
                disabled={couponLoading || Boolean(cart.cupon)}
              />

              {cart.cupon ? (
                <button className="btn-ghost" type="button" onClick={removeCoupon} disabled={couponLoading}>
                  {couponLoading ? (t.loading || 'Cargando...') : (t.removeCoupon || 'Quitar cupón')}
                </button>
              ) : (
                <button className="btn-neon" type="button" onClick={applyCoupon} disabled={couponLoading}>
                  {couponLoading ? (t.loading || 'Cargando...') : (t.apply || 'Aplicar')}
                </button>
              )}
            </div>

            {couponError && <div className="alert error">{couponError}</div>}

            {cart.cupon && (
              <div className="alert success">
                {(t.appliedCoupon || 'Cupón aplicado')}: {cart.cupon}
              </div>
            )}
          </section>

          <div className="cart-total cart-total-breakdown">
            <div>
              <span>{t.subtotal || 'Subtotal'}</span>
              <strong>S/ {toNumber(cart.subtotal).toFixed(2)}</strong>
            </div>

            <div>
              <span>{t.discount || 'Descuento'}</span>
              <strong>- S/ {toNumber(cart.descuento).toFixed(2)}</strong>
            </div>

            <div>
              <span>{t.total}</span>
              <strong>S/ {toNumber(cart.total).toFixed(2)}</strong>
            </div>
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
