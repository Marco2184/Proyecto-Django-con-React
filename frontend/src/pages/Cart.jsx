import ProductImage from '../components/ProductImage'
import { imageOf } from '../services/productImage'
import { useEffect, useState } from 'react'
import { api, getApiError } from '../services/api'
import { localizedSpecValue, getTranslatedPlatform, getTranslatedSpec, getTranslatedText } from '../i18n'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

export default function Cart({ t, user, onNavigate, onCartChange, snapshot }) {
  const [cart, setCart] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)
  const [preview, setPreview] = useState(null)
  const [couponCode, setCouponCode] = useState('')
  const [couponLoading, setCouponLoading] = useState(false)
  const [couponError, setCouponError] = useState('')
  const [updating, setUpdating] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(()=>{if(snapshot) {setCart(snapshot);setCouponCode(snapshot.cupon || '')}},[snapshot])

  const updateCart = (data) => {
    setCart(data)
    setCouponCode(data.cupon || '')
    onCartChange?.(data)
  }

  useEffect(() => {
    let cancelled = false

    if (!user) {
      onNavigate('login')
      return
    }

    const load = async () => {
      try {
        setError('')
        const { data } = await api.get('/cart/')

        if (cancelled) return

        setCart(data)
        setCouponCode(data.cupon || '')
        onCartChange?.(data)
        // No hacemos otra solicitud desde App.jsx.
      } catch (err) {
        if (!cancelled) setError(getApiError(err))
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [user?.id, retry])

  const patch = async (id, accion) => {
    if (updating) return

    try {
      setUpdating(true)
      setError('')
      setNotice(null)

      const { data } = await api.patch(`/cart/items/${id}/`, { accion })
      updateCart(data)
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setUpdating(false)
    }
  }

  const remove = async (id) => {
    if (updating) return

    const ok = window.confirm(t.confirmRemoveCartItem)
    if (!ok) return

    try {
      setUpdating(true)
      setError('')
      setNotice(null)

      const { data } = await api.delete(`/cart/items/${id}/`)
      updateCart(data)

      setNotice({ type: 'success', key: 'cartItemRemoved' })
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setUpdating(false)
    }
  }

  const clear = async () => {
    if (updating) return

    const ok = window.confirm(t.confirmClearCart)
    if (!ok) return

    try {
      setUpdating(true)
      setError('')
      setNotice(null)
      setCouponError('')

      const { data } = await api.post('/cart/clear/')
      updateCart(data)

      setNotice({ type: 'success', key: 'cartCleared' })
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setUpdating(false)
    }
  }

  const applyCoupon = async () => {
    if (couponLoading) return

    try {
      setCouponLoading(true)
      setCouponError('')
      setNotice(null)

      const { data } = await api.post('/cart/aplicar-cupon/', {
        codigo: couponCode.trim()
      })

      updateCart(data)
    } catch (err) {
      setCouponError(getApiError(err))
    } finally {
      setCouponLoading(false)
    }
  }

  const removeCoupon = async () => {
    if (couponLoading) return

    try {
      setCouponLoading(true)
      setCouponError('')
      setNotice(null)

      const { data } = await api.post('/cart/quitar-cupon/')
      updateCart(data)
    } catch (err) {
      setCouponError(getApiError(err))
    } finally {
      setCouponLoading(false)
    }
  }

  const checkout = () => {
    if (!updating) onNavigate('checkout')
  }

  if (error) {
    return (
      <div className="panel-page">
        <div className="alert error">{getTranslatedText(t, error)}</div>
        <button className="btn-neon" onClick={() => setRetry(value=>value+1)}>{t.retry}</button>
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
        <div className="alert warn" key={getTranslatedText(t, message)}>
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
                <ProductImage
                  src={imageOf(item.producto)}
                  alt={getTranslatedText(t, item.producto.nombre)}
                  onClick={() => setPreview(imageOf(item.producto))}
                />

                <div>
                  <button
                    className="link-reset prod-name"
                    onClick={() => onNavigate('detail', { productId: item.producto.id })}
                  >
                    {getTranslatedText(t, item.producto.nombre)}
                  </button>

                  <div className="muted">
                    {t.currentPrice} S/ {toNumber(item.producto.precio).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}
                    {' · '}
                    {t.subtotal} S/ {toNumber(item.subtotal).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}
                  </div>

                  <div className="muted">
                    {t.stockAvailable}: {item.producto.stock}
                    {' · '}
                    {t.inCart}: {item.cantidad}
                  </div>

                  <div className="muted">
                    {item.producto.plataformas?.map(
                      (platform) => getTranslatedPlatform(t, platform)
                    ).join(', ')}
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
                          {getTranslatedSpec(t, key)}: {localizedSpecValue(t, key, value)}
                        </span>
                      ))}
                  </div>
                </div>

                <div className="qty">
                  <button
                    disabled={updating}
                    onClick={() => patch(item.id, 'menos')}
                  >
                    −
                  </button>

                  <span>{item.cantidad}</span>

                  <button
                    onClick={() => patch(item.id, 'mas')}
                    disabled={updating || item.cantidad >= item.producto.stock}
                  >
                    +
                  </button>
                </div>

                <button
                  className="btn-ghost"
                  disabled={updating}
                  onClick={() => remove(item.id)}
                >
                  {t.delete}
                </button>
              </div>
            ))}
          </div>

          <section className="panel-card cart-coupon-panel">
            <h2>{t.discountCode}</h2>

            <div className="cart-coupon-row">
              <input
                className="input-m"
                value={couponCode}
                onChange={(event) => setCouponCode(event.target.value.toUpperCase())}
                placeholder={t.discountCodePlaceholder}
                disabled={couponLoading || updating || Boolean(cart.cupon)}
              />

              {cart.cupon ? (
                <button
                  className="btn-ghost"
                  type="button"
                  onClick={removeCoupon}
                  disabled={couponLoading || updating}
                >
                  {couponLoading ? (t.loading) : (t.removeCoupon)}
                </button>
              ) : (
                <button
                  className="btn-neon"
                  type="button"
                  onClick={applyCoupon}
                  disabled={couponLoading || updating}
                >
                  {couponLoading ? (t.loading) : (t.apply)}
                </button>
              )}
            </div>

            {couponError && <div className="alert error">{getTranslatedText(t, couponError)}</div>}

            {cart.cupon && (
              <div className="alert success">
                {(t.appliedCoupon)}: {cart.cupon}
              </div>
            )}
          </section>

          <div className="cart-total cart-total-breakdown">
            <div>
              <span>{t.subtotal}</span>
              <strong>S/ {toNumber(cart.subtotal).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
            </div>

            <div>
              <span>{t.discount}</span>
              <strong>- S/ {toNumber(cart.descuento).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
            </div>

            <div>
              <span>{t.total}</span>
              <strong>S/ {toNumber(cart.total).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
            </div>
          </div>

          <div className="row-actions">
            <button className="btn-ghost" disabled={updating} onClick={clear}>
              {t.empty}
            </button>

            <button
              className="btn-neon"
              onClick={checkout}
              disabled={
                updating ||
                cart.vacio ||
                (cart.items || []).some((item) => item.stock_insuficiente)
              }
            >
              {t.confirmOrder}
            </button>
          </div>
        </>
      )}

      {preview && (
        <div className="image-modal" onClick={() => setPreview(null)}>
          <ProductImage src={preview} alt={t.imagePreview} />
          <button className="btn-ghost">{t.close}</button>
        </div>
      )}
    </div>
  )
}
