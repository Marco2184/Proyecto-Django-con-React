import { useEffect, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

export default function DetallePedido({ t, user, orderId, onNavigate }) {
  const [order, setOrder] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async () => {
    try {
      setError('')
      const { data } = await api.get(`/profile/orders/${orderId}/`)
      setOrder(data)
    } catch (err) {
      setError(getApiError(err))
    }
  }

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }
    if (orderId) load()
  }, [user, orderId])

  const cancelOrder = async () => {
    const ok = window.confirm('¿Seguro que quieres cancelar este pedido?')
    if (!ok) return
    try {
      setNotice('')
      const { data } = await api.post(`/profile/orders/${orderId}/cancel/`, { motivo: 'Cancelado por el cliente' })
      setOrder(data)
      setNotice('Pedido cancelado correctamente.')
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const getReceiptPdf = async () => {
    const { data } = await api.get(`/profile/orders/${orderId}/receipt/`, { responseType: 'blob' })
    return new Blob([data], { type: 'application/pdf' })
  }

  const downloadReceipt = async () => {
    try {
      const pdf = await getReceiptPdf()
      const url = window.URL.createObjectURL(pdf)
      const link = document.createElement('a')
      link.href = url
      link.download = `comprobante-${order.numero}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const printReceipt = async () => {
    try {
      setError('')
      const pdf = await getReceiptPdf()
      const url = window.URL.createObjectURL(pdf)

      const previousFrame = document.getElementById('monolith-receipt-print-frame')
      if (previousFrame) previousFrame.remove()

      const iframe = document.createElement('iframe')
      iframe.id = 'monolith-receipt-print-frame'
      iframe.title = 'Comprobante Monolith'
      iframe.src = url
      iframe.style.position = 'fixed'
      iframe.style.right = '0'
      iframe.style.bottom = '0'
      iframe.style.width = '0'
      iframe.style.height = '0'
      iframe.style.border = '0'
      iframe.style.opacity = '0'

      iframe.onload = () => {
        window.setTimeout(() => {
          try {
            iframe.contentWindow?.focus()
            iframe.contentWindow?.print()
          } catch (printError) {
            setError('No se pudo abrir la impresión automática. Descarga el comprobante y ábrelo para imprimirlo.')
          } finally {
            window.setTimeout(() => {
              iframe.remove()
              window.URL.revokeObjectURL(url)
            }, 60000)
          }
        }, 700)
      }

      document.body.appendChild(iframe)
    } catch (err) {
      setError(getApiError(err))
    }
  }

  if (error) return <div className="panel-page checkout-page"><div className="alert error">{error}</div></div>
  if (!order) return <div className="loading-m">{t.loading || 'Cargando...'}</div>

  return (
    <div className="panel-page checkout-page">
      <div className="section-tag">Sprint 4 // Detalle</div>
      <h1>{order.numero}</h1>

      {notice && <div className="alert success">{notice}</div>}

      <div className="checkout-grid detail-grid">
        <section className="panel-card checkout-card">
          <h2>Estado del pedido</h2>
          <span className={`status-pill ${order.estado}`}>{order.estado}</span>
          <p className="muted">Pago: {order.metodo_pago} / {order.estado_pago}</p>
          <p className="muted">Entrega estimada: {order.fecha_estimada_entrega || '-'}</p>
          <p className="muted">Dirección: {order.direccion_texto || '-'}</p>

          <div className="timeline-list">
            {(order.timeline || []).map((event) => (
              <div className="timeline-item" key={event.id}>
                <strong>{event.estado}</strong>
                <span>{event.descripcion}</span>
                <small>{new Date(event.creado_en).toLocaleString('es-PE')}</small>
              </div>
            ))}
          </div>
        </section>

        <section className="panel-card checkout-card">
          <h2>Productos</h2>
          {(order.items || []).map((item) => (
            <div className="summary-row" key={item.id}>
              <span>{item.producto_nombre} x{item.cantidad}</span>
              <strong>S/ {toNumber(item.subtotal).toFixed(2)}</strong>
            </div>
          ))}
          <div className="summary-total">
            <span>{t.total}</span>
            <strong>S/ {toNumber(order.monto_total).toFixed(2)}</strong>
          </div>
        </section>

        <aside className="panel-card checkout-summary">
          <h2>Acciones</h2>
          <button className="btn-neon" onClick={downloadReceipt}>Descargar comprobante</button>
          <button className="btn-ghost" onClick={printReceipt}>Imprimir</button>
          {order.puede_cancelar ? (
            <button className="btn-ghost danger" onClick={cancelOrder}>Cancelar pedido</button>
          ) : (
            <div className="alert warn">{order.motivo_no_cancelable || 'Este pedido ya no puede cancelarse.'}</div>
          )}
          <button className="btn-outline-neon" onClick={() => onNavigate('misPedidos')}>Volver a mis pedidos</button>
        </aside>
      </div>
    </div>
  )
}
