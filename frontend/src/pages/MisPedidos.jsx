import { formatDate } from '../i18n'
import { getTranslatedText } from '../i18n'
import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'
import { getTranslatedOrderStatus } from '../i18n'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

export default function MisPedidos({ t, user, onNavigate, searchParams, onQuery, lang }) {
  const [orders, setOrders] = useState([])
  const [summary, setSummary] = useState([])
  const params = new URLSearchParams(searchParams)
  const estado = params.get('estado') || ''
  const search = params.get('search') || ''
  const setEstado = value => onQuery({estado:value})
  const setSearch = value => onQuery({search:value}, {replace:true})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        setLoading(true)
        setError('')
        const params = {}
        if (estado) params.estado = estado
        if (search.trim()) params.search = search.trim()
        const { data } = await api.get('/profile/orders/', {
          params,
          signal: controller.signal
        })
        if (controller.signal.aborted) return
        setOrders(data.results || (Array.isArray(data) ? data : []))
        setSummary(data.resumen_mensual || [])
      } catch (err) {
        if (!controller.signal.aborted && err.code !== 'ERR_CANCELED') {
          setError(getApiError(err))
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, search.trim() ? 300 : 0)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [user?.id, estado, search])

  const grouped = useMemo(() => {
    return orders.reduce((acc, order) => {
      const key = new Date(order.fecha).toLocaleDateString(lang === 'en' ? 'en-US' : 'es-PE', { year: 'numeric', month: 'long' })
      if (!acc[key]) acc[key] = []
      acc[key].push(order)
      return acc
    }, {})
  }, [orders, lang])



  return (
    <div className="panel-page checkout-page">
      <div className="section-tag">{t.ordersTag}</div>
      <h1>{t.myOrders}</h1>

      {error && <div className="alert error">{getTranslatedText(t, error)}</div>}

      <div className="orders-toolbar">
        <input className="input-m" placeholder={t.searchOrders} aria-label={t.searchOrders} value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input-m" aria-label={t.orderStatusLabel} value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">{t.orderAll}</option>
          <option value="pendiente">{t.orderPending}</option>
          <option value="procesando">{t.orderProcessing}</option>
          <option value="enviado">{t.orderShipped}</option>
          <option value="entregado">{t.orderDelivered}</option>
          <option value="cancelado">{t.orderCancelled}</option>
        </select>
      </div>

      {summary.length > 0 && (
        <div className="monthly-summary">
          {summary.map((item) => (
            <div className="summary-chip" key={new Date(item.mes + '-01T12:00:00').toLocaleDateString(lang === 'en' ? 'en-US' : 'es-PE', {year:'numeric',month:'long'})}>
              <strong>{new Date(item.mes + '-01T12:00:00').toLocaleDateString(lang === 'en' ? 'en-US' : 'es-PE', {year:'numeric',month:'long'})}</strong>
              <span>{item.cantidad} {t.orders} · S/ {toNumber(item.total).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</span>
            </div>
          ))}
        </div>
      )}

      {loading && <div className="loading-m" role="status">{t.loading}</div>}
      {!loading && (orders.length === 0 ? (
        <div className="empty-state"><h3>{t.noRegisteredOrders}</h3></div>
      ) : (
        Object.entries(grouped).map(([month, items]) => (
          <section className="orders-group" key={month}>
            <h2>{month}</h2>
            <div className="orders-list">
              {items.map((order) => (
                <div className="order-card" key={order.id}>
                  <div>
                    <strong>{order.numero}</strong>
                    <p className="muted">{new Date(order.fecha).toLocaleString(lang === 'en' ? 'en-US' : 'es-PE')} · {order.items_count} {t.productsLabel}</p>
                    <span className={`status-pill ${order.estado}`}>{getTranslatedOrderStatus(t, order.estado)}</span>
                  </div>
                  <div className="order-card-right">
                    <strong>S/ {toNumber(order.monto_total).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</strong>
                    <button className="btn-outline-neon" onClick={() => onNavigate('detallePedido', { orderId: order.id })}>
                      {t.viewDetail}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))
      ))}
    </div>
  )
}
