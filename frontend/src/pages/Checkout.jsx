import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'

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

export default function Checkout({ t, user, onNavigate, onCartChange }) {
  const [cart, setCart] = useState(null)
  const [addresses, setAddresses] = useState([])
  const [addressMode, setAddressMode] = useState('saved')
  const [selectedAddress, setSelectedAddress] = useState('')
  const [address, setAddress] = useState({
    calle: '', ciudad: '', departamento: 'Arequipa', codigo_postal: '', predeterminada: true
  })
  const [metodoPago, setMetodoPago] = useState('tarjeta')
  const [payment, setPayment] = useState({ numero_tarjeta: '', nombre_tarjeta: '', vencimiento: '', cvv: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const hasSavedAddress = addresses.length > 0

  const canPay = useMemo(() => {
    if (!cart || cart.vacio) return false
    if (addressMode === 'saved' && !selectedAddress) return false
    if (addressMode === 'new' && (!address.calle || !address.ciudad || !address.departamento || !address.codigo_postal)) return false
    if (metodoPago === 'tarjeta') {
      const digits = payment.numero_tarjeta.replace(/\D/g, '')
      const cvv = payment.cvv.replace(/\D/g, '')
      return digits.length >= 12 && cvv.length >= 3
    }
    return true
  }, [cart, addressMode, selectedAddress, address, metodoPago, payment])

  const load = async () => {
    try {
      setError('')
      const [cartRes, addressRes] = await Promise.all([
        api.get('/cart/'),
        api.get('/profile/addresses/')
      ])
      setCart(cartRes.data)
      const list = addressRes.data || []
      setAddresses(list)
      const defaultAddress = list.find((item) => item.predeterminada) || list[0]
      if (defaultAddress) {
        setSelectedAddress(String(defaultAddress.id))
        setAddressMode('saved')
      } else {
        setAddressMode('new')
      }
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

  const confirmCheckout = async () => {
    try {
      setLoading(true)
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

      const { data } = await api.post('/cart/checkout/', payload)
      onCartChange?.()
      onNavigate('pedidoConfirmado', { orderId: data.pedido.id, pedido: data.pedido })
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setLoading(false)
    }
  }

  if (error) {
    return (
      <div className="panel-page checkout-page">
        <div className="alert error">{error}</div>
        <button className="btn-ghost" onClick={() => onNavigate('cart')}>{t.backToCart || 'Volver al carrito'}</button>
      </div>
    )
  }

  if (!cart) return <div className="loading-m">{t.loading || 'Cargando...'}</div>

  return (
    <div className="panel-page checkout-page">
      <div className="section-tag">Sprint 4 // Checkout</div>
      <h1>{t.checkout || 'Checkout'}</h1>

      {cart.vacio ? (
        <div className="empty-state">
          <h3>{t.emptyCart}</h3>
          <button className="btn-neon" onClick={() => onNavigate('catalog')}>{t.goToCatalog}</button>
        </div>
      ) : (
        <div className="checkout-grid">
          <section className="panel-card checkout-card">
            <h2>{t.shippingAddress || 'Dirección de envío'}</h2>

            {hasSavedAddress && (
              <label className="checkout-radio">
                <input type="radio" checked={addressMode === 'saved'} onChange={() => setAddressMode('saved')} />
                {t.useSavedAddress || 'Usar dirección guardada'}
              </label>
            )}

            {addressMode === 'saved' && hasSavedAddress && (
              <select className="input-m" value={selectedAddress} onChange={(e) => setSelectedAddress(e.target.value)}>
                {addresses.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.calle}, {item.ciudad} ({item.departamento})
                  </option>
                ))}
              </select>
            )}

            <label className="checkout-radio">
              <input type="radio" checked={addressMode === 'new'} onChange={() => setAddressMode('new')} />
              {t.newAddress || 'Nueva dirección'}
            </label>

            {addressMode === 'new' && (
              <div className="checkout-form-grid">
                <input className="input-m" placeholder={t.street || 'Calle'} value={address.calle} onChange={(e) => setAddress({ ...address, calle: e.target.value })} />
                <input className="input-m" placeholder={t.city || 'Ciudad'} value={address.ciudad} onChange={(e) => setAddress({ ...address, ciudad: e.target.value })} />
                <select className="input-m" value={address.departamento} onChange={(e) => setAddress({ ...address, departamento: e.target.value })}>
                  {departamentos.map((dep) => <option key={dep} value={dep}>{dep}</option>)}
                </select>
                <input className="input-m" placeholder={t.postalCode || 'Código postal'} value={address.codigo_postal} onChange={(e) => setAddress({ ...address, codigo_postal: e.target.value })} />
                <label className="checkout-check">
                  <input type="checkbox" checked={address.predeterminada} onChange={(e) => setAddress({ ...address, predeterminada: e.target.checked })} />
                  {t.defaultAddress || 'Predeterminada'}
                </label>
              </div>
            )}
          </section>

          <section className="panel-card checkout-card">
            <h2>{t.paymentMethod || 'Método de pago'}</h2>
            <div className="payment-tabs">
             <button className={metodoPago === 'tarjeta' ? 'active' : ''} onClick={() => setMetodoPago('tarjeta')}>
              {t.card || 'Tarjeta'}
            </button>
            <button className={metodoPago === 'transferencia' ? 'active' : ''} onClick={() => setMetodoPago('transferencia')}>
              {t.transfer || 'Transferencia'}
            </button>
            </div>

            {metodoPago === 'tarjeta' ? (
              <div className="checkout-form-grid">
                <input className="input-m" placeholder={t.cardNumber || 'Número de tarjeta'} value={payment.numero_tarjeta} onChange={(e) => setPayment({ ...payment, numero_tarjeta: e.target.value })} />
                <input className="input-m" placeholder={t.cardName || 'Nombre en tarjeta'} value={payment.nombre_tarjeta} onChange={(e) => setPayment({ ...payment, nombre_tarjeta: e.target.value })} />
                <input className="input-m" placeholder={t.cardExpiration || 'MM/AA'} value={payment.vencimiento} onChange={(e) => setPayment({ ...payment, vencimiento: e.target.value })} />
                <input className="input-m" placeholder={t.cardCvv || 'CVV'} value={payment.cvv} onChange={(e) => setPayment({ ...payment, cvv: e.target.value })} />
              </div>
            ) : (
              <div className="alert success">
                {t.transferInfo || 'Pago por transferencia simulado. El sistema aprobará el pedido automáticamente para el trabajo.'}
              </div>
            )}
          </section>

          <aside className="panel-card checkout-summary">
            <h2>{t.orderSummary || 'Resumen del pedido'}</h2>
            {(cart.items || []).map((item) => (
              <div className="summary-row" key={item.id}>
                <span>{item.producto.nombre} x{item.cantidad}</span>
                <strong>S/ {toNumber(item.subtotal).toFixed(2)}</strong>
              </div>
            ))}
            <div className="summary-total">
              <span>{t.total}</span>
              <strong>S/ {toNumber(cart.total).toFixed(2)}</strong>
            </div>
            <button className="btn-neon" disabled={!canPay || loading} onClick={confirmCheckout}>
              {loading ? (t.processing || 'Procesando...') : (t.payAndConfirm || 'Pagar y confirmar')}
            </button>
            <button className="btn-ghost" onClick={() => onNavigate('cart')}>{t.backToCart || 'Volver al carrito'}</button>
          </aside>
        </div>
      )}
    </div>
  )
}
