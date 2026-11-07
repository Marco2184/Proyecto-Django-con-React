import { formatDate } from '../i18n'
import { getTranslatedText } from '../i18n'
import { useEffect, useState } from 'react'
import { api, getApiError } from '../services/api'

export default function PedidoConfirmado({t,orderId,onNavigate}) {
  const [pedido,setPedido]=useState(null), [error,setError]=useState('')
  useEffect(()=>{
    const controller=new AbortController()
    api.get(`/profile/orders/${orderId}/`,{signal:controller.signal}).then(({data})=>{if (!controller.signal.aborted) setPedido(data)})
      .catch(err=>{if (!controller.signal.aborted) setError(getApiError(err))})
    return ()=>controller.abort()
  },[orderId])
  return <div className="panel-page checkout-page"><div className="panel-card confirmed-card">
    <h1>{t.orderConfirmed}</h1>
    {error ? <div className="alert error" role="alert">{getTranslatedText(t, error)}</div> : !pedido ? <p role="status">{t.loading}</p> : <>
      <p>{t.confirmationText} <strong>{pedido.numero}</strong></p>
      <p className="muted">{t.estimatedDelivery}: {formatDate(pedido.fecha_estimada_entrega, t)}</p>
    </>}
    <div className="row-actions"><button className="btn-neon" onClick={()=>onNavigate('detallePedido',{orderId})}>{t.viewOrderDetail}</button>
    <button className="btn-ghost" onClick={()=>onNavigate('misPedidos')}>{t.myOrders}</button></div>
  </div></div>
}
