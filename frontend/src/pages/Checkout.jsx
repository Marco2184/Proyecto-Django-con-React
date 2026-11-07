import { getTranslatedText } from '../i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'
import useDraft from '../hooks/useDraft'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

const departamentos = [
  'Amazonas', 'Áncash', 'Apurímac', 'Arequipa', 'Ayacucho', 'Cajamarca', 'Callao',
  'Cusco', 'Huancavelica', 'Huánuco', 'Ica', 'Junín', 'La Libertad', 'Lambayeque',
  'Lima', 'Loreto', 'Madre de Dios', 'Moquegua', 'Pasco', 'Piura', 'Puno',
  'San Martín', 'Tacna', 'Tumbes', 'Ucayali'
]

export default function Checkout({ t, user, onNavigate, onCartChange, snapshot }) {
  const [cart, setCart] = useState(null)
  useEffect(()=>{if(snapshot) setCart(snapshot)},[snapshot])
  const [addresses, setAddresses] = useState([])
  const [addressMode, setAddressMode] = useDraft(`monolith-draft:checkout-mode:${user.id}`, 'saved')
  const [selectedAddress, setSelectedAddress] = useDraft(`monolith-draft:checkout-selected:${user.id}`, '')
  const [address, setAddress] = useDraft(`monolith-draft:checkout:${user.id}`, {
    calle: '', ciudad: '', departamento: 'Arequipa', codigo_postal: '', predeterminada: true
  })
  const [metodoPago, setMetodoPago] = useState('tarjeta')
  const [payment] = useState({ numero_tarjeta: '4111111111111111', nombre_tarjeta: 'MONOLITH DEMO', vencimiento: '12/30', cvv: '123' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [paymentStatus, setPaymentStatus] = useState('idle')
  const paymentLock = useRef(false)
  const checkoutKey = useRef(sessionStorage.getItem(`monolith-checkout:${user.id}`)||crypto.randomUUID())

  const hasSavedAddress = addresses.length > 0

  const canPay = useMemo(() => {
    if(!user.email_verificado) return false
    if (!cart || cart.vacio) return false
    if (addressMode === 'saved' && !selectedAddress) return false
    if (addressMode === 'new' && (!address.calle || !address.ciudad || !address.departamento || !address.codigo_postal)) return false
    if (metodoPago === 'tarjeta') {
      const digits = payment.numero_tarjeta.replace(/\D/g, '')
      const cvv = payment.cvv.replace(/\D/g, '')
      return digits.length >= 12 && cvv.length >= 3
    }
    return true
  }, [cart, addressMode, selectedAddress, address, metodoPago, payment,user.email_verificado])

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    const controller = new AbortController()
    const load = async () => {
      try {
        setError('')
        const [cartRes, addressRes] = await Promise.all([
          api.get('/cart/', { signal: controller.signal }),
          api.get('/profile/addresses/', { signal: controller.signal })
        ])
        if (controller.signal.aborted) return

        setCart(cartRes.data)
        onCartChange?.(cartRes.data)
        const raw = addressRes.data
        const list = Array.isArray(raw) ? raw : (raw?.results || [])
        setAddresses(list)
        const defaultAddress = list.find((item) => item.predeterminada) || list[0]
        if (defaultAddress) {
          setSelectedAddress(current => list.some(item => String(item.id) === current) ? current : String(defaultAddress.id))
        } else {
          setAddressMode('new')
        }
      } catch (err) {
        if (!controller.signal.aborted && err.code !== 'ERR_CANCELED') {
          setError(getApiError(err))
        }
      }
    }

    load()
    return () => controller.abort()
  }, [user?.id])

  const confirmCheckout = async () => {
    if (paymentLock.current || !canPay) return
    paymentLock.current = true
    try {
      setLoading(true)
      setPaymentStatus('processing')
      setError('')


      const payload = {
        metodo_pago: metodoPago,
        pago: metodoPago === 'tarjeta' ? payment : { referencia: 'transferencia-simulada' }
      }

      if (addressMode === 'saved') {
        payload.direccion_id = Number(selectedAddress)
      } else {
        payload.direccion = address
      }

      sessionStorage.setItem(`monolith-checkout:${user.id}`,checkoutKey.current)
      const { data } = await api.post('/cart/checkout/', payload,{headers:{'Idempotency-Key':checkoutKey.current}})
      sessionStorage.removeItem(`monolith-checkout:${user.id}`)

      setPaymentStatus('approved')
      sessionStorage.removeItem(`monolith-draft:checkout:${user.id}`)
      sessionStorage.removeItem(`monolith-draft:checkout-mode:${user.id}`)
      sessionStorage.removeItem(`monolith-draft:checkout-selected:${user.id}`)
      await new Promise((resolve) => window.setTimeout(resolve, 300))

      onCartChange?.(data.carrito)
      onNavigate('pedidoConfirmado', { orderId: data.pedido.id, pedido: data.pedido })
    } catch (err) {
      setPaymentStatus('idle')
      setError(getApiError(err))
    } finally {
      paymentLock.current = false
      setLoading(false)
    }
  }

  if (error) {
    return (
      <div className="panel-page checkout-page">
        <div className="alert error">{getTranslatedText(t, error)}</div>
        <button className="btn-ghost" onClick={() => onNavigate('cart')}>{t.backToCart}</button>
      </div>
    )
  }

  if (!cart) return <div className="loading-m">{t.loading}</div>

  return (
    <div className="panel-page checkout-page">
      <div className="section-tag">{t.checkoutTag}</div>
      <h1>{t.checkout}</h1>

      {cart.vacio ? (
        <div className="empty-state">
          <h3>{t.emptyCart}</h3>
          <button className="btn-neon" onClick={() => onNavigate('catalog')}>{t.goToCatalog}</button>
        </div>
      ) : (
        <div className="checkout-grid">
          <section className="panel-card checkout-card">
            <h2>{t.shippingAddress}</h2>

            {hasSavedAddress && (
              <label className="checkout-radio">
                <input type="radio" checked={addressMode === 'saved'} onChange={() => setAddressMode('saved')} />
                {t.useSavedAddress}
              </label>
            )}

            {addressMode === 'saved' && hasSavedAddress && (
              <select className="input-m" aria-label={t.shippingAddress} value={selectedAddress} onChange={(e) => setSelectedAddress(e.target.value)}>
                {addresses.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.calle}, {item.ciudad} ({item.departamento})
                  </option>
                ))}
              </select>
            )}

            <label className="checkout-radio">
              <input type="radio" checked={addressMode === 'new'} onChange={() => setAddressMode('new')} />
              {t.newAddress}
            </label>

            {addressMode === 'new' && (
              <div className="checkout-form-grid">
                <input className="input-m" aria-label={t.street} placeholder={t.street} value={address.calle} onChange={(e) => setAddress({ ...address, calle: e.target.value })} />
                <input className="input-m" aria-label={t.city} placeholder={t.city} value={address.ciudad} onChange={(e) => setAddress({ ...address, ciudad: e.target.value })} />
                <select className="input-m" aria-label={t.department} value={address.departamento} onChange={(e) => setAddress({ ...address, departamento: e.target.value })}>
                  {departamentos.map((dep) => <option key={dep} value={dep}>{dep}</option>)}
                </select>
                <input className="input-m" aria-label={t.postalCode} placeholder={t.postalCode} value={address.codigo_postal} onChange={(e) => setAddress({ ...address, codigo_postal: e.target.value })} />
                <label className="checkout-check">
                  <input type="checkbox" checked={address.predeterminada} onChange={(e) => setAddress({ ...address, predeterminada: e.target.checked })} />
                  {t.defaultAddress}
                </label>
              </div>
            )}
          </section>

          <section className="panel-card checkout-card">
            <h2>{t.paymentMethod}</h2>
            <div className="payment-tabs">
             <button className={metodoPago === 'tarjeta' ? 'active' : ''} onClick={() => setMetodoPago('tarjeta')}>
              {t.card}
            </button>
            <button className={metodoPago === 'transferencia' ? 'active' : ''} onClick={() => setMetodoPago('transferencia')}>
              {t.transfer}
            </button>
            </div>

            {metodoPago === 'tarjeta' ? (
              <div className="checkout-form-grid">
                <p className="muted">{t.simulatedPaymentOnly}</p>
                <input className="input-m" aria-label={t.cardNumber} placeholder={t.cardNumber} value={payment.numero_tarjeta} readOnly />
                <input className="input-m" aria-label={t.cardName} placeholder={t.cardName} value={payment.nombre_tarjeta} readOnly />
                <input className="input-m" aria-label={t.cardExpiration} placeholder={t.cardExpiration} value={payment.vencimiento} readOnly />
                <input className="input-m" aria-label={t.cardCvv} placeholder={t.cardCvv} value={payment.cvv} readOnly />
              </div>
            ) : (
              <div className="alert success">
                {t.transferInfo}
              </div>
            )}
          </section>

          <aside className="panel-card checkout-summary">
            <h2>{t.orderSummary}</h2>
            {(cart.items || []).map((item) => (
              <div className="summary-row" key={item.id}>
                <span>{getTranslatedText(t, item.producto.nombre)} x{item.cantidad}</span>
                <strong>S/ {toNumber(item.subtotal).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
              </div>
            ))}
            <div className="summary-row">
              <span>{t.subtotal}</span>
              <strong>S/ {toNumber(cart.subtotal).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
            </div>

            {toNumber(cart.descuento) > 0 && (
              <div className="summary-row checkout-discount-row">
                <span>{t.discount} {cart.cupon ? `(${cart.cupon})` : ''}</span>
                <strong>- S/ {toNumber(cart.descuento).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
              </div>
            )}

            <div className="summary-total">
              <span>{t.total}</span>
              <strong>S/ {toNumber(cart.total).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
            </div>
            <button className="btn-neon" disabled={!canPay || loading} onClick={confirmCheckout}>
              {loading ? (t.processing) : (t.payAndConfirm)}
            </button>
            <button className="btn-ghost" onClick={() => onNavigate('cart')}>{t.backToCart}</button>
          </aside>
        </div>
      )}

      {paymentStatus !== 'idle' && (
        <div className="payment-overlay" role="status" aria-live="polite">
          <div className="payment-modal panel-card">
            {paymentStatus === 'processing' ? (
              <>
                <div className="payment-spinner" />
                <h2>{t.processingPayment}</h2>
                <p>{t.fakeGatewayInfo}</p>
              </>
            ) : (
              <>
                <div className="payment-approved">✅</div>
                <h2>{t.paymentApproved}</h2>
                <p>{t.creatingOrder}</p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
