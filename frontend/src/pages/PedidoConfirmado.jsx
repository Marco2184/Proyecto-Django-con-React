export default function PedidoConfirmado({ t, orderId, pedido, onNavigate }) {
  const numero = pedido?.numero || `#${orderId || ''}`

  return (
    <div className="panel-page checkout-page">
      <div className="panel-card confirmed-card">
        <div className="section-tag">Sprint 4 // Pedido confirmado</div>
        <h1>{t.orderConfirmed || 'Pedido confirmado'}</h1>
        <p className="muted">Tu pedido {numero} fue creado correctamente.</p>
        {pedido?.fecha_estimada_entrega && (
          <p className="muted">Entrega estimada: {pedido.fecha_estimada_entrega}</p>
        )}
        <div className="row-actions">
          <button className="btn-neon" onClick={() => onNavigate('detallePedido', { orderId })}>
            {t.viewOrderDetail || 'Ver detalle'}
          </button>
          <button className="btn-ghost" onClick={() => onNavigate('misPedidos')}>
            {t.myOrders || 'Mis pedidos'}
          </button>
        </div>
      </div>
    </div>
  )
}
