import { imageOf } from '../services/productImage'
import {useState} from 'react'
import {useWishlist,WishButton} from '../components/WishlistContext'
import ProductImage from '../components/ProductImage'
import {api,getApiError} from '../services/api'

export default function Wishlist({t,onNavigate,onCartChange}) {
  const w=useWishlist(),[error,setError]=useState(''),[busy,setBusy]=useState(null),[status,setStatus]=useState('')
  const add=async id=>{if(busy)return;setBusy(id);setError('');try{const {data}=await api.post('/cart/add/',{producto_id:id,cantidad:1});onCartChange(data);setStatus(t.addedToCart)}catch(e){setError(getApiError(e))}finally{setBusy(null)}}
  if(w.available===false)return <section className="panel-page"><h1>{t.wishlist}</h1><p className="alert warn" role="status">{t.wishlistUnavailable}</p></section>
  return <section className="panel-page"><h1>{t.wishlist}</h1>{(error||w.error)&&<p className="alert error" role="alert">{error||w.error}</p>}{status&&<p className="alert success" role="status">{status}</p>}
    <button className="btn-ghost" onClick={()=>w.load()}>{t.refreshStatus}</button>
    <section className="panel-card"><h2>{t.priceDrops}</h2>{!w.notifications.length&&<p className="muted">{t.noNotifications}</p>}{w.notifications.map(n=><article key={n.id}><button className="link-neon" onClick={()=>onNavigate('detail',{productId:n.producto_id})}>{n.nombre}</button><p>{t.previousPrice}: S/ {n.precio_anterior} → {t.currentPrice}: S/ {n.precio_actual}</p><button className="btn-ghost" onClick={()=>w.read(n.id)}>{t.markRead}</button></article>)}</section>
    {w.loading?<p role="status">{t.loading}</p>:!w.items.length?<div className="empty-state"><p>{t.wishlistEmpty}</p><button className="btn-neon" onClick={()=>onNavigate('catalog')}>{t.backToCatalog}</button></div>:<div className="products-grid">{w.items.map(({producto:p})=><article className="prod-card" key={p.id}><button className="prod-img link-reset" onClick={()=>onNavigate('detail',{productId:p.id})}><ProductImage src={imageOf(p)} alt={p.nombre}/></button><div className="prod-body"><h2>{p.nombre}</h2><p>S/ {p.precio}</p><WishButton id={p.id} t={t} onNavigate={onNavigate}/><button className="btn-neon" disabled={!p.disponible||busy!==null} onClick={()=>add(p.id)}>{busy===p.id?t.loading:t.addCart}</button></div></article>)}</div>}
    <div className="row-actions"><button className="btn-ghost" disabled={!w.previous||w.loading} onClick={()=>w.setPage(p=>p-1)}>{t.previousPage}</button><span>{t.page} {w.page}</span><button className="btn-ghost" disabled={!w.next||w.loading} onClick={()=>w.setPage(p=>p+1)}>{t.nextPage}</button></div>
  </section>
}
