import { imageOf } from '../services/productImage'
import {WishButton} from '../components/WishlistContext'
import { getTranslatedText } from '../i18n'
import { getTranslatedCategory, getTranslatedPlatform, getTranslatedSpec, localizedDescription, localizedSpecValue } from '../i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, catalogApi, getApiError } from '../services/api'
import ProductImage from '../components/ProductImage'

function ProductMini({ p, onNavigate, onAdd, t }) {
  const img = imageOf(p)
  return <div className="mini-prod detail-mini-prod" key={p.id}>
    <button className="mini-img-btn" onClick={() => onNavigate('detail', { productId: p.id })} aria-label={getTranslatedText(t, p.nombre)}>
      <ProductImage className="mini-img" src={img} alt={getTranslatedText(t, p.nombre)} />
    </button>
    <div className="mini-prod-info">
      <button className="link-reset prod-name" onClick={() => onNavigate('detail', { productId: p.id })}>{getTranslatedText(t, p.nombre)}</button>
      <div className="muted">S/ {parseFloat(p.precio).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})} · {t.stock} {p.stock}</div>
    </div>
    <button className="btn-outline-neon" onClick={() => onAdd(p.id)} disabled={!p.disponible}>{t.addCart}</button>
  </div>
}

export default function ProductDetail({ t, productId, onNavigate, user, onCartChange }) {
  const [p, setP] = useState(null)
  const [activeImg, setActiveImg] = useState('')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [addError,setAddError] = useState('')
  const [adding,setAdding] = useState(false)
  const addingRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    setP(null); setError(''); setMsg('')
    catalogApi.get(`/productos/${productId}/`, {signal:controller.signal}).then(({data}) => {
      if (controller.signal.aborted) return
      setP(data)
      const firstGallery = (data.galeria || [])[0]
      setActiveImg(imageOf(data) || (!data.portada ? firstGallery?.url || firstGallery?.imagen : '') || '')
    }).catch(err => {if (!controller.signal.aborted) setError(getApiError(err))})
    return () => controller.abort()
  }, [productId])

  const gallery = useMemo(() => {
    if (!p) return []
    const imgs = []
    if (imageOf(p)) imgs.push({ id: 'main', url: imageOf(p) })
    ;(p.galeria || []).forEach(g => imgs.push({ id: g.id, url: g.url || g.imagen }))
    return imgs.filter(x => x.url)
  }, [p])

  const add = async (id = p.id) => {
    if (!user) return onNavigate('login', {next:window.location.pathname})
    if (addingRef.current) return
    addingRef.current = true; setAdding(true); setAddError('')
    try { const {data} = await api.post('/cart/add/', { producto_id: id, cantidad: 1 }); setMsg(t.addedToCart); onCartChange?.(data) }
    catch (err) { setAddError(getApiError(err)) }
    finally {addingRef.current=false; setAdding(false)}
  }

  if (error) return <div className="panel-page"><div className="alert error">{getTranslatedText(t, error)}</div><button className="btn-ghost" onClick={() => onNavigate('catalog')}>{t.back}</button></div>
  if (!p) return <div className="loading-m" role="status">{t.loadingProduct}</div>

  return <div className="panel-page">
    <button className="btn-ghost" onClick={() => onNavigate('catalog')}>{t.backToCatalog}</button>
    {msg && <div className="alert success">{getTranslatedText(t, msg)}</div>}
    {addError && <div className="alert error" role="alert">{getTranslatedText(t, addError)}</div>}
    <div className="detail-grid">
      <div>
        <div className="detail-img"><ProductImage src={activeImg} alt={getTranslatedText(t, p.nombre)} loading="eager" /></div>
        {gallery.length > 1 && <div className="gallery-strip">{gallery.map(img => <button key={img.id} className={activeImg === img.url ? 'active' : ''} onClick={() => setActiveImg(img.url)}><ProductImage src={img.url} alt={t.productImage} /></button>)}</div>}
      </div>
      <div>
        <div className="section-tag">{t.productDetail}</div>
        <h1>{getTranslatedText(t, p.nombre)}</h1>
        <div className="prod-badges">{(p.plataformas || []).map(pl => <span className="badge-plat" key={pl.id}>{getTranslatedPlatform(t, pl)}</span>)}{p.categoria && <span className="badge-plat">{getTranslatedCategory(t, p.categoria)}</span>}</div>
        <div className="detail-price">S/ {parseFloat(p.precio).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})} {p.tiene_descuento && <><span className="prod-price-orig">S/ {parseFloat(p.precio_original).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</span><span className="prod-discount">-{p.porcentaje_descuento}%</span></>}</div>
        <p className="muted detail-desc">{localizedDescription(t, p)}</p>
        <div className={`prod-stock ${p.disponible ? 'in-stock' : 'out-stock'}`}>{p.disponible ? `${t.available} (${p.stock})` : t.outStock}</div>
        <div className="spec-panel">{Object.entries(p.especificaciones || {}).length === 0 ? <div><strong>{t.specs}</strong><span>{t.notAvailable}</span></div> : Object.entries(p.especificaciones || {}).map(([k,v]) => <div key={k}><strong>{getTranslatedSpec(t, k)}</strong><span>{localizedSpecValue(t, k, v)}</span></div>)}</div>
        <WishButton id={p.id} t={t} onNavigate={onNavigate}/><button className="btn-neon" onClick={() => add(p.id)} disabled={!p.disponible || adding}>{adding ? t.loading : t.addCart}</button>
      </div>
    </div>

    <section className="panel-card detail-recommend-panel"><h2>{t.similarProducts}</h2><div className="mini-products-grid detail-mini-grid">{(p.productos_similares || []).length === 0 ? <div className="muted">{t.noSimilar}</div> : p.productos_similares.map(x => <ProductMini key={x.id} p={x} onNavigate={onNavigate} onAdd={add} t={t} />)}</div></section>
    <section className="panel-card detail-recommend-panel"><h2>{t.frequentlyBought}</h2><div className="mini-products-grid detail-mini-grid">{(p.comprados_juntos || []).length === 0 ? <div className="muted">{t.noBundles}</div> : p.comprados_juntos.map(x => <ProductMini key={x.id} p={x} onNavigate={onNavigate} onAdd={add} t={t} />)}</div></section>
  </div>
}
