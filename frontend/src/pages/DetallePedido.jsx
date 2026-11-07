import { formatDate } from '../i18n'
import { useEffect, useRef, useState } from 'react'
import { api, getApiError } from '../services/api'
import './Checkout.css'
import { getTranslatedOrderStatus, getTranslatedPaymentStatus, getTranslatedText } from '../i18n'

function toNumber(value) {
  const number = Number.parseFloat(value)
  return Number.isFinite(number) ? number : 0
}

export default function DetallePedido({ t, user, orderId, onNavigate, lang }) {
  const [order, setOrder] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const [receiptLoading, setReceiptLoading] = useState(false)

  const cancellingRef = useRef(false)

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    if (!orderId) return

    const controller = new AbortController()

    const load = async () => {
      try {
        setError('')
        setNotice('')
        setOrder(null)

        const { data } = await api.get(
          `/profile/orders/${orderId}/`,
          { signal: controller.signal }
        )

        if (!controller.signal.aborted) {
          setOrder(data)
        }
      } catch (err) {
        if (
          controller.signal.aborted ||
          err.code === 'ERR_CANCELED'
        ) return

        setError(getApiError(err))
      }
    }

    load()

    return () => controller.abort()
  }, [user?.id, orderId])

  const cancelOrder = async () => {
    if (cancellingRef.current || !order?.puede_cancelar) return

    const ok = window.confirm(
      t.confirmCancelOrder
    )

    if (!ok) return

    cancellingRef.current = true

    try {
      setCancelling(true)
      setError('')
      setNotice('')

      const { data } = await api.post(
        `/profile/orders/${orderId}/cancel/`,
        {
          motivo: 'Cancelado por el cliente'
        }
      )

      setOrder(data)
      setNotice(t.orderCancelledNotice)

    } catch (err) {
      setError(getApiError(err))

    } finally {
      cancellingRef.current = false
      setCancelling(false)
    }
  }

  const getReceiptPdf = async () => {
    const { data } = await api.get(
      `/profile/orders/${orderId}/receipt/`,
      {
        responseType: 'blob'
      }
    )

    return new Blob([data], {
      type: 'application/pdf'
    })
  }

  const downloadReceipt = async () => {
    if (receiptLoading) return

    try {
      setReceiptLoading(true)
      setError('')

      const pdf = await getReceiptPdf()
      const url = window.URL.createObjectURL(pdf)

      const link = document.createElement('a')

      link.href = url
      link.download = `${t.receiptPrefix}-${order.numero}.pdf`

      document.body.appendChild(link)
      link.click()
      link.remove()

      window.setTimeout(() => {
        window.URL.revokeObjectURL(url)
      }, 1000)

    } catch (err) {
      setError(getApiError(err))

    } finally {
      setReceiptLoading(false)
    }
  }

  const printReceipt = async () => {
    if (receiptLoading) return

    try {
      setReceiptLoading(true)
      setError('')

      const pdf = await getReceiptPdf()
      const url = window.URL.createObjectURL(pdf)

      const previousFrame = document.getElementById(
        'monolith-receipt-print-frame'
      )

      if (previousFrame) {
        previousFrame.remove()
      }

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
            setError(
              t.printUnavailable
            )

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

    } finally {
      setReceiptLoading(false)
    }
  }

  if (!order) {
    if (error) {
      return (
        <div className="panel-page checkout-page">
          <div className="alert error" role="alert">{getTranslatedText(t, error)}</div>

          <button
            className="btn-ghost"
            onClick={() => onNavigate('misPedidos')}
          >
            {t.backToOrders}
          </button>
        </div>
      )
    }

    return (
      <div className="loading-m">
        {t.loading}
      </div>
    )
  }

  return (
    <div className="panel-page checkout-page">

      <div className="section-tag">
        {t.orderDetailTag}
      </div>

      <h1>{order.numero}</h1>

      {error && (
        <div className="alert error" role="alert">
          {getTranslatedText(t, error)}
        </div>
      )}

      {notice && (
        <div className="alert success" role="status">
          {getTranslatedText(t, notice)}
        </div>
      )}

      <div className="checkout-grid detail-grid">

        <section className="panel-card checkout-card">

          <h2>{t.orderStatusLabel}</h2>

          <span className={`status-pill ${order.estado}`}>
            {getTranslatedOrderStatus(t, order.estado)}
          </span>

          <p className="muted">
            {t.paymentMethod}: {order.metodo_pago === 'tarjeta' ? t.card : t.transfer} / {getTranslatedPaymentStatus(t, order.estado_pago)}
          </p>

          <p className="muted">
            {t.estimatedDelivery}: {formatDate(order.fecha_estimada_entrega, t)}
          </p>

          <p className="muted">
            {t.shippingAddress}: {order.direccion_texto || '-'}
          </p>

          <div className="timeline-list">
            {(order.timeline || []).map((event) => (
              <div
                className="timeline-item"
                key={event.id}
              >
                <strong>{getTranslatedOrderStatus(t, event.estado)}</strong>

                <span>{getTranslatedText(t, event.descripcion) || t.timelineUpdate}</span>

                <small>
                  {new Date(event.creado_en).toLocaleString(lang === 'en' ? 'en-US' : 'es-PE')}
                </small>
              </div>
            ))}
          </div>

        </section>

        <section className="panel-card checkout-card">

          <h2>{t.productsLabel}</h2>

          {(order.items || []).map((item) => (
            <div
              className="summary-row"
              key={item.id}
            >
              <span>
                {getTranslatedText(t, item.producto_nombre)} x{item.cantidad}
              </span>

              <strong>
                S/ {toNumber(item.subtotal).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}
              </strong>
            </div>
          ))}

          <div className="summary-total">

            <span>{t.total}</span>

            <strong>
              S/ {toNumber(order.monto_total).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}
            </strong>

          </div>

        </section>

        <aside className="panel-card checkout-summary">

          <h2>{t.actions}</h2>

          <button
            className="btn-neon"
            onClick={downloadReceipt}
            disabled={receiptLoading}
          >
            {receiptLoading
              ? t.preparingReceipt
              : t.downloadReceipt}
          </button>

          <button
            className="btn-ghost"
            onClick={printReceipt}
            disabled={receiptLoading}
          >
            {t.printReceipt}
          </button>

          {order.puede_cancelar ? (
            <button
              className="btn-ghost danger"
              onClick={cancelOrder}
              disabled={cancelling}
            >
              {cancelling
                ? t.cancellingOrder
                : t.cancelOrder}
            </button>
          ) : (
            <div className="alert warn">
              {getTranslatedText(t, order.motivo_no_cancelable) || t.cannotCancelOrder}
            </div>
          )}

          <button
            className="btn-outline-neon"
            onClick={() => onNavigate('misPedidos')}
            disabled={cancelling}
          >
            {t.backToOrders}
          </button>

        </aside>

      </div>
    </div>
  )
}
