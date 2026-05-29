import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'

function ProductMini({ p, onNavigate, onAdd, t }) {
  const img = p.imagen_url || p.imagen_principal || ''
  return <div className="mini-prod detail-mini-prod" key={p.id}>
    <button className="mini-img-btn" onClick={() => onNavigate('detail', { productId: p.id })} aria-label={p.nombre}>
      {img ? <img className="mini-img" src={img} alt={p.nombre} loading="lazy" /> : <span className="mini-img-placeholder">MONOLITH</span>}
    </button>
    <div className="mini-prod-info">
      <button className="link-reset prod-name" onClick={() => onNavigate('detail', { productId: p.id })}>{p.nombre}</button>
      <div className="muted">S/ {parseFloat(p.precio).toFixed(2)} · {t.stock} {p.stock}</div>
    </div>
    <button className="btn-outline-neon" onClick={() => onAdd(p.id)} disabled={!p.disponible}>{t.addCart}</button>
  </div>
}

export default function ProductDetail({ t, productId, onNavigate, user, onCartChange }) {
  const [p, setP] = useState(null)
  const [activeImg, setActiveImg] = useState('')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    setP(null); setError(''); setMsg('')
    api.get(`/productos/${productId}/`).then(({data}) => {
      setP(data)
      const firstGallery = (data.galeria || [])[0]
      setActiveImg(firstGallery?.url || firstGallery?.imagen || data.imagen_url || data.imagen_principal || '')
    }).catch(err => setError(getApiError(err)))
  }, [productId])

  const gallery = useMemo(() => {
    if (!p) return []
    const imgs = []
    if (p.imagen_url || p.imagen_principal) imgs.push({ id: 'main', url: p.imagen_url || p.imagen_principal })
    ;(p.galeria || []).forEach(g => imgs.push({ id: g.id, url: g.url || g.imagen }))
    return imgs.filter(x => x.url)
  }, [p])

  const add = async (id = p.id) => {
    if (!user) return onNavigate('login')
    try { await api.post('/cart/add/', { producto_id: id, cantidad: 1 }); setMsg('Producto agregado al carrito.'); onCartChange?.() }
    catch (err) { setError(getApiError(err)) }
  }

  if (error) return <div className="panel-page"><div className="alert error">{error}</div><button className="btn-ghost" onClick={() => onNavigate('catalog')}>Volver</button></div>
  if (!p) return <div className="loading-m">LOADING PRODUCT...</div>

  return <div className="panel-page">
    <button className="btn-ghost" onClick={() => onNavigate('catalog')}>← Catálogo</button>
    {msg && <div className="alert success">{msg}</div>}
    <div className="detail-grid">
      <div>
        <div className="detail-img">{activeImg ? <img src={activeImg} alt={p.nombre} /> : 'MONOLITH'}</div>
        {gallery.length > 1 && <div className="gallery-strip">{gallery.map(img => <button key={img.id} className={activeImg === img.url ? 'active' : ''} onClick={() => setActiveImg(img.url)}><img src={img.url} alt="Producto" /></button>)}</div>}
      </div>
      <div>
        <div className="section-tag">Producto // Detalle</div>
        <h1>{p.nombre}</h1>
        <div className="prod-badges">{(p.plataformas || []).map(pl => <span className="badge-plat" key={pl.id}>{pl.nombre}</span>)}{p.categoria && <span className="badge-plat">{p.categoria.nombre}</span>}</div>
        <div className="detail-price">S/ {parseFloat(p.precio).toFixed(2)} {p.tiene_descuento && <><span className="prod-price-orig">S/ {parseFloat(p.precio_original).toFixed(2)}</span><span className="prod-discount">-{p.porcentaje_descuento}%</span></>}</div>
        <p className="muted detail-desc">{p.descripcion || 'Sin descripción.'}</p>
        <div className={`prod-stock ${p.disponible ? 'in-stock' : 'out-stock'}`}>{p.disponible ? `${t.available} (${p.stock})` : t.outStock}</div>
        <div className="spec-panel">{Object.entries(p.especificaciones || {}).length === 0 ? <div><strong>Specs</strong><span>N/D</span></div> : Object.entries(p.especificaciones || {}).map(([k,v]) => <div key={k}><strong>{k}</strong><span>{v}</span></div>)}</div>
        <button className="btn-neon" onClick={() => add(p.id)} disabled={!p.disponible}>{t.addCart}</button>
      </div>
    </div>

    <section className="panel-card detail-recommend-panel"><h2>{t.similarProducts}</h2><div className="mini-products-grid detail-mini-grid">{(p.productos_similares || []).length === 0 ? <div className="muted">{t.noSimilar}</div> : p.productos_similares.map(x => <ProductMini key={x.id} p={x} onNavigate={onNavigate} onAdd={add} t={t} />)}</div></section>
    <section className="panel-card detail-recommend-panel"><h2>{t.frequentlyBought}</h2><div className="mini-products-grid detail-mini-grid">{(p.comprados_juntos || []).length === 0 ? <div className="muted">{t.noBundles}</div> : p.comprados_juntos.map(x => <ProductMini key={x.id} p={x} onNavigate={onNavigate} onAdd={add} t={t} />)}</div></section>
  </div>
}
