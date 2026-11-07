import {WishButton} from '../components/WishlistContext'
import { getTranslatedText } from '../i18n'
import { useState, useEffect, useRef, useMemo } from 'react'
import { api, catalogApi, getApiError } from '../services/api'
import { catalogMetadata } from '../services/catalogMetadata'
import { getTranslatedCategory, getTranslatedPlatform } from '../i18n'
import { PAGE_SIZE, readCatalog, catalogParams, visiblePages } from '../catalogState'
import AppLink from '../components/AppLink'
import ProductImage from '../components/ProductImage'
import { imageOf } from '../services/productImage'

export default function Catalog({t,onNavigate,user,onCartChange,cartQuantities,searchParams,onQuery}) {
  const filters=useMemo(()=>readCatalog(searchParams),[searchParams])
  const params=useMemo(()=>catalogParams(filters),[filters])
  const [search,setSearch]=useState(filters.q)
  const [prices,setPrices]=useState({min:filters.min,max:filters.max})
  const [products,setProducts]=useState([]), [total,setTotal]=useState(0)
  const [loading,setLoading]=useState(true), [error,setError]=useState('')
  const [loadedParams,setLoadedParams]=useState(null)
  const pending=loading || loadedParams!==params
  const [platforms,setPlatforms]=useState([]), [categories,setCategories]=useState([])
  const [metadataError,setMetadataError]=useState(''), [notice,setNotice]=useState('')
  const [noticeError,setNoticeError]=useState(false)
  const [retry,setRetry]=useState(0), [busy,setBusy]=useState(null)
  const [filtersOpen,setFiltersOpen]=useState(()=>!window.matchMedia('(max-width: 1000px)').matches)
  const busyRef=useRef(false), searchBoxRef=useRef(null)
  const [suggestions,setSuggestions]=useState([]), [suggestOpen,setSuggestOpen]=useState(false)
  const [suggestLoading,setSuggestLoading]=useState(false), [active,setActive]=useState(-1)
  const pageCount=Math.ceil(total/PAGE_SIZE)
  const change=values=>onQuery({...values,page:null})
  const reset=()=>{
    onQuery({search:null,plataforma:[],categoria:null,precio_min:null,precio_max:null,sort:null,page:null})
    if (!searchParams) setRetry(n=>n+1)
  }

  useEffect(()=>{setSearch(filters.q); setSuggestOpen(false)},[filters.q])
  useEffect(()=>setPrices({min:filters.min,max:filters.max}),[filters.min,filters.max])
  useEffect(()=>{
    const controller=new AbortController()
    setLoading(true); setError('')
    catalogApi.get('/productos/?'+params,{signal:controller.signal}).then(({data})=>{
      if (controller.signal.aborted) return
      setProducts(data.results || data); setTotal(data.count ?? data.length); setLoadedParams(params)
    }).catch(err=>{if (!controller.signal.aborted) {setError(getApiError(err)); setLoadedParams(params)}})
      .finally(()=>{if (!controller.signal.aborted) setLoading(false)})
    return ()=>controller.abort()
  },[params,retry])
  useEffect(()=>{
    let current=true
    catalogMetadata().then(([p,c])=>{if (current) {setPlatforms(p); setCategories(c); setMetadataError('')}})
      .catch(()=>{if (current) setMetadataError(t.filtersUnavailable)})
    return ()=>{current=false}
  },[retry,t.filtersUnavailable])
  useEffect(()=>{
    const controller=new AbortController(), q=search.trim()
    setActive(-1); setSuggestions([]); setSuggestOpen(false); setSuggestLoading(false)
    if (q.length<2 || q===filters.q) return ()=>controller.abort()
    const timer=setTimeout(async ()=>{
      setSuggestLoading(true); setSuggestOpen(true)
      try {
        const suggestionParams=new URLSearchParams(params)
        suggestionParams.delete('search'); suggestionParams.delete('page'); suggestionParams.set('q',q)
        const {data}=await catalogApi.get('/productos/buscar/?'+suggestionParams,{signal:controller.signal})
        if (!controller.signal.aborted) setSuggestions(data.resultados || [])
      } catch {if (!controller.signal.aborted) setSuggestions([])}
      finally {if (!controller.signal.aborted) setSuggestLoading(false)}
    },300)
    return ()=>{clearTimeout(timer); controller.abort()}
  },[search,params,filters.q])
  useEffect(()=>{
    const close=event=>{if (!searchBoxRef.current?.contains(event.target)) setSuggestOpen(false)}
    document.addEventListener('pointerdown',close)
    return ()=>document.removeEventListener('pointerdown',close)
  },[])
  const applySearch=()=>{
    if (search.trim().length===1) {setNoticeError(true); setNotice(t.searchMinimum); return}
    setNotice(''); setSuggestOpen(false); change({search:search.trim() || null})
  }
  const applyPrices=event=>{
    event.preventDefault()
    if ((prices.min && Number(prices.min)<0) || (prices.max && Number(prices.max)<0) ||
        (prices.min!=='' && prices.max!=='' && Number(prices.min)>Number(prices.max))) {setNoticeError(true); setNotice(t.priceRangeInvalid); return}
    setNotice(''); change({precio_min:prices.min,precio_max:prices.max})
  }
  const addToCart=async id=>{
    if (!user) return onNavigate('login',{next:window.location.pathname+window.location.search})
    if (busyRef.current) return
    busyRef.current=true; setBusy(id); setNotice(''); setNoticeError(false)
    try {const {data}=await api.post('/cart/add/',{producto_id:id,cantidad:1}); onCartChange(data); setNotice(t.addedToCart)}
    catch (err) {setNoticeError(true); setNotice(getApiError(err))}
    finally {busyRef.current=false; setBusy(null)}
  }
  const openProduct=id=>{setSuggestOpen(false); onNavigate('detail',{productId:id})}

  return <div className="catalog-layout">
    <aside className="catalog-sidebar" aria-label={t.filters}>
      <details className="mobile-filters" open={filtersOpen} onToggle={e=>setFiltersOpen(e.currentTarget.open)}><summary>{t.filters}</summary>
        {metadataError && <div className="alert error" role="alert">{metadataError}<button className="btn-ghost" onClick={()=>{setRetry(n=>n+1)}}>{t.retry}</button></div>}
        <fieldset><legend className="filter-title">{t.platform}</legend>
          {platforms.map(platform=><label key={platform.slug} className={`filter-label ${filters.platforms.includes(platform.slug)?'active-filter':''}`}>
            <input type="checkbox" checked={filters.platforms.includes(platform.slug)} onChange={()=>change({plataforma:filters.platforms.includes(platform.slug)?filters.platforms.filter(p=>p!==platform.slug):[...filters.platforms,platform.slug]})} />{getTranslatedPlatform(t,platform)}
          </label>)}
        </fieldset>
        <fieldset><legend className="filter-title">{t.category}</legend>
          <label className="filter-label"><input type="radio" name="category" checked={!filters.category} onChange={()=>change({categoria:null})} />{t.all}</label>
          {categories.flatMap(category=>[category,...(category.subcategorias || [])]).map(category=><label key={category.slug} className={`filter-label ${filters.category===category.slug?'active-filter':''}`}>
            <input type="radio" name="category" checked={filters.category===category.slug} onChange={()=>change({categoria:category.slug})} />{getTranslatedCategory(t,category)}
          </label>)}
        </fieldset>
        <form className="price-filter" onSubmit={applyPrices}><fieldset><legend className="filter-title">{t.priceRange}</legend>
          <label>{t.minimumPrice}<input className="input-m" type="number" min="0" max="99999999.99" step="0.01" value={prices.min} onChange={e=>setPrices({...prices,min:e.target.value})} /></label>
          <label>{t.maximumPrice}<input className="input-m" type="number" min="0" max="99999999.99" step="0.01" value={prices.max} onChange={e=>setPrices({...prices,max:e.target.value})} /></label>
          <button className="btn-outline-neon" type="submit">{t.applyFilters}</button>
        </fieldset></form>
        <button className="btn-ghost" onClick={reset}>{t.resetFilters}</button>
      </details>
    </aside>
    <section className="catalog-main" aria-busy={pending}>
      <div className="catalog-header"><div><div className="section-tag">{t.productsCatalog}</div><h1>{t.catalog}</h1>
        <p className="muted" role="status" aria-live="polite">{pending?t.loadingCatalog:`${total} ${t.found}`}</p></div>
        <label className="sort-row">{t.sort}<select className="catalog-sort" value={filters.sort} onChange={e=>change({sort:e.target.value})}>
          <option value="popularidad">{filters.q?t.relevance:t.popular}</option><option value="precio_asc">{t.priceAsc}</option><option value="precio_desc">{t.priceDesc}</option><option value="recientes">{t.recent}</option>
        </select></label>
      </div>
      <div className="search-bar-wrap" ref={searchBoxRef}><div className="search-row"><div className="search-input-wrap">
        <input className="search-input-m" role="combobox" aria-label={t.search} aria-autocomplete="list" aria-expanded={suggestOpen} aria-controls="catalog-suggestions" aria-activedescendant={active>=0?`suggest-${active}`:undefined}
          placeholder={t.searchPlaceholder} value={search} maxLength={150} onChange={e=>setSearch(e.target.value)}
          onKeyDown={event=>{
            if (event.key==='Escape') {setSuggestOpen(false); setActive(-1)}
            if (event.key==='ArrowDown' || event.key==='ArrowUp') {event.preventDefault(); setSuggestOpen(true); setActive(n=>Math.max(0,Math.min(suggestions.length-1,n+(event.key==='ArrowDown'?1:-1))))}
            if (event.key==='Enter') {event.preventDefault(); if (suggestOpen && suggestions[active]) openProduct(suggestions[active].id); else applySearch()}
          }} />
        {suggestOpen && <div className="steam-suggest" id="catalog-suggestions" role="listbox" aria-label={t.suggestionsTitle}>
          {suggestLoading?<div className="suggest-empty" role="status">{t.loading}</div>:suggestions.length===0?<div className="suggest-empty">{t.noSuggestions}</div>:suggestions.map((product,index)=><button type="button" role="option" aria-selected={active===index} id={`suggest-${index}`} key={product.id} className="suggest-item" onClick={()=>openProduct(product.id)}>
            <ProductImage src={imageOf(product)} alt="" /><span><strong>{getTranslatedText(t, product.nombre)}</strong><em>S/ {Number(product.precio).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</em></span>
          </button>)}
        </div>}
      </div><button className="btn-neon" onClick={applySearch}>{t.search}</button>{search && <button className="btn-ghost" onClick={()=>{setSearch(''); change({search:null})}}>{t.clear}</button>}</div></div>
      {notice && <div className={`alert ${noticeError?'error':'success'}`} role={noticeError?'alert':'status'}>{getTranslatedText(t, notice)}</div>}
      {error?<div className="alert error" role="alert">{getTranslatedText(t, error)}<div className="row-actions"><button className="btn-neon" onClick={()=>setRetry(n=>n+1)}>{t.retry}</button><button className="btn-ghost" onClick={reset}>{t.resetFilters}</button></div></div>:pending?<div className="loading-m" role="status">{t.loadingCatalog}</div>:products.length===0?
        <div className="empty-state"><h2>{t.noResults}</h2><button className="btn-outline-neon" onClick={reset}>{t.resetFilters}</button></div>:<>
          <div className="products-grid">{products.map(product=><article className="prod-card" key={product.id}>
            <AppLink className="prod-img" page="detail" payload={{productId:product.id}} onNavigate={onNavigate} aria-label={getTranslatedText(t, product.nombre)}><ProductImage src={imageOf(product)} alt={getTranslatedText(t, product.nombre)} /></AppLink>
            <div className="prod-body"><WishButton id={product.id} t={t} onNavigate={onNavigate}/><div className="prod-badges">{(product.plataformas || []).slice(0,2).map(p=><span className="badge-plat" key={p.slug}>{getTranslatedPlatform(t,p)}</span>)}
              {cartQuantities[product.id]>0 && <span className="badge-cart">{t.inCart}: {cartQuantities[product.id]}</span>}
              {product.tiene_descuento && <span className="prod-discount">-{product.porcentaje_descuento}%</span>}</div>
              <AppLink className="prod-name link-reset" page="detail" payload={{productId:product.id}} onNavigate={onNavigate}>{getTranslatedText(t, product.nombre)}</AppLink>
              <div className="prod-price">S/ {Number(product.precio).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}{product.tiene_descuento && <span className="prod-price-orig">S/ {Number(product.precio_original).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}</span>}</div>
              <div className={`prod-stock ${product.disponible?'in-stock':'out-stock'}`}><span className="stock-dot" />{product.disponible?`${t.available} (${product.stock})`:t.outStock}</div>
              <button className="btn-outline-neon card-btn" onClick={()=>addToCart(product.id)} disabled={!product.disponible || busy!==null} aria-label={`${t.addCart}: ${getTranslatedText(t, product.nombre)}`}>{busy===product.id?t.loading:t.addCart}</button>
            </div></article>)}</div>
          <nav className="catalog-pagination" aria-label={t.pagination}>
            <p>{t.showing} {(filters.page-1)*PAGE_SIZE+1}–{Math.min(filters.page*PAGE_SIZE,total)} / {total}</p>
            <div className="pagination-controls"><button className="btn-ghost" disabled={filters.page===1} onClick={()=>onQuery({page:filters.page-1})}>{t.previousPage}</button>
              {visiblePages(filters.page,pageCount).map((page,index,array)=><span key={page}>{index>0 && page-array[index-1]>1 && <span className="page-ellipsis">…</span>}<button className="btn-ghost" aria-label={`${t.page} ${page}`} aria-current={page===filters.page?'page':undefined} onClick={()=>onQuery({page})}>{page}</button></span>)}
              <button className="btn-ghost" disabled={filters.page>=pageCount} onClick={()=>onQuery({page:filters.page+1})}>{t.nextPage}</button></div>
          </nav></>}
    </section>
  </div>
}
