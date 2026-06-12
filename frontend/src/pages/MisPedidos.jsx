import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

export default function MisPedidos({ t, user, onNavigate }) {
  const [orders, setOrders] = useState([])
  const [summary, setSummary] = useState([])
  const [estado, setEstado] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      setLoading(true)
      setError('')
      const params = {}
      if (estado) params.estado = estado
      if (search.trim()) params.search = search.trim()
      const { data } = await api.get('/profile/orders/', { params })
      setOrders(data.results || data || [])
      setSummary(data.resumen_mensual || [])
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }
    const timer = window.setTimeout(load, 250)
    return () => window.clearTimeout(timer)
  }, [user, estado, search])

  const grouped = useMemo(() => {
    return orders.reduce((acc, order) => {
      const key = new Date(order.fecha).toLocaleDateString('es-PE', { year: 'numeric', month: 'long' })
      if (!acc[key]) acc[key] = []
      acc[key].push(order)
      return acc
    }, {})
  }, [orders])

  if (loading) return <div className="loading-m">{t.loading || 'Cargando...'}</div>

  return (
    <div className="panel-page checkout-page">
      <div className="section-tag">Sprint 4 // Historial</div>
      <h1>{t.myOrders || 'Mis pedidos'}</h1>

      {error && <div className="alert error">{error}</div>}

      <div className="orders-toolbar">
        <input className="input-m" placeholder="Buscar por número de pedido" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input-m" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">{t.orderAll || 'Todos'}</option>
          <option value="pendiente">{t.orderPending || 'Pendiente'}</option>
          <option value="procesando">{t.orderProcessing || 'Procesando'}</option>
          <option value="enviado">{t.orderShipped || 'Enviado'}</option>
          <option value="entregado">{t.orderDelivered || 'Entregado'}</option>
          <option value="cancelado">{t.orderCancelled || 'Cancelado'}</option>
        </select>
      </div>

      {summary.length > 0 && (
        <div className="monthly-summary">
          {summary.map((item) => (
            <div className="summary-chip" key={item.mes}>
              <strong>{item.mes}</strong>
              <span>{item.cantidad} pedidos · S/ {toNumber(item.total).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {orders.length === 0 ? (
        <div className="empty-state"><h3>{t.noRegisteredOrders || 'Sin pedidos registrados.'}</h3></div>
      ) : (
        Object.entries(grouped).map(([month, items]) => (
          <section className="orders-group" key={month}>
            <h2>{month}</h2>
            <div className="orders-list">
              {items.map((order) => (
                <div className="order-card" key={order.id}>
                  <div>
                    <strong>{order.numero}</strong>
                    <p className="muted">{new Date(order.fecha).toLocaleString('es-PE')} · {order.items_count} items</p>
                    <span className={`status-pill ${order.estado}`}>{order.estado}</span>
                  </div>
                  <div className="order-card-right">
                    <strong>S/ {toNumber(order.monto_total).toFixed(2)}</strong>
                    <button className="btn-outline-neon" onClick={() => onNavigate('detallePedido', { orderId: order.id })}>
                      {t.viewDetail || 'Ver detalle'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  )
}
