import { formatDate } from '../i18n'
import { getTranslatedText } from '../i18n'
import {useEffect,useRef,useState} from 'react'
import {api,AUTH_BASE_URL} from '../services/api'
import {chatText} from '../chatText'
import {getTranslatedCategory,getTranslatedOrderStatus} from '../i18n'

export default function ChatPanel({open,onClose,user,lang,t,onNavigate,onVisit,onCartChange,toggleLang}) {
  const words=chatText[lang], dialog=useRef(null), inputRef=useRef(null), end=useRef(null)
  const [input,setInput]=useState(''), [messages,setMessages]=useState([]), [loading,setLoading]=useState(false)
  const [pending,setPending]=useState(null), [adding,setAdding]=useState(false), [notice,setNotice]=useState('')
  const [selected,setSelected]=useState([])
  const context=useRef({}), request=useRef(null), busy=useRef(false), addingRef=useRef(false)
  const clear=()=>{
    request.current?.abort(); context.current={};busy.current=false;addingRef.current=false
    setMessages([]);setInput('');setSelected([]);setPending(null);setLoading(false);setAdding(false);setNotice('')
  }
  useEffect(()=>{clear()},[user?.id,lang])
  useEffect(()=>()=>request.current?.abort(),[])
  useEffect(()=>{if(open) {if(!dialog.current.open) dialog.current.showModal();inputRef.current?.focus()} else dialog.current?.close()},[open])
  useEffect(()=>{if(open) end.current?.scrollIntoView({block:'nearest',behavior:'instant'})},[messages,loading,pending,open])
  const close=()=>{dialog.current?.close();onClose()}
  const navigate=(page,payload)=>{onNavigate(page,payload);close()}
  const action=entry=>{
    if(entry.page==='catalog' && entry.filters) {
      const f=entry.filters, params=new URLSearchParams()
      if(f.search) params.set('search',f.search)
      if(f.category) params.set('categoria',f.category)
      for(const value of f.platforms || []) params.append('plataforma',value)
      if(f.min) params.set('precio_min',f.min)
      if(f.max) params.set('precio_max',f.max)
      onVisit('/'+(params.size?'?'+params.toString():''));close()
    } else navigate(entry.page,entry.page==='login'?{next:'/pedidos'}:undefined)
  }
  const send=async(message=input,compareIds=[])=>{
    if(busy.current || addingRef.current) return
    if(!message.trim()) {setNotice(words.empty);return}
    const controller=new AbortController();request.current=controller;busy.current=true
    setInput('');setNotice('');setLoading(true);setPending(null)
    setMessages(previous=>[...previous.slice(-18),{role:'user',text:message}])
    try {
      const {data}=await api.post('/assistant/chat',{message,language:lang,context:context.current,compare_ids:compareIds},
        {baseURL:AUTH_BASE_URL,signal:controller.signal,timeout:15000})
      if(controller.signal.aborted) return
      context.current=data.context || {};setSelected([])
      setMessages(previous=>[...previous,{role:'assistant',...data}])
    } catch(error) {
      if(controller.signal.aborted) return
      setMessages(previous=>[...previous,{role:'assistant',text:error.response?.data?.detail || words.error,error:true,retry:{message,compareIds},
        actions:error.response?.status===401?[{page:'login'}]:[]}])
    } finally {if(!controller.signal.aborted) {busy.current=false;setLoading(false)}}
  }
  const askAdd=product=>{
    if(!user) {navigate('login',{next:window.location.pathname+window.location.search});return}
    setNotice('');setPending(product)
  }
  const confirmAdd=async()=>{
    if(!pending || addingRef.current || busy.current) return
    addingRef.current=true;setAdding(true);setNotice('')
    const controller=new AbortController();request.current=controller
    try {
      const {data}=await api.post('/cart/add/',{producto_id:pending.id,cantidad:1},{signal:controller.signal})
      if(controller.signal.aborted) return
      onCartChange(data);setNotice(words.added);setPending(null)
    } catch(error) {if(!controller.signal.aborted) setNotice(error.response?.data?.detail || words.addError)}
    finally {if(!controller.signal.aborted) {addingRef.current=false;setAdding(false)}}
  }
  return <dialog ref={dialog} className="monolith-chat" aria-labelledby="monolith-chat-title" aria-describedby="monolith-chat-mode" onCancel={event=>{event.preventDefault();close()}}
    onKeyDown={event=>{
      if(event.key!=='Tab') return
      const controls=[...dialog.current.querySelectorAll('button:not(:disabled),textarea:not(:disabled),input:not(:disabled),[tabindex="0"]')].filter(node=>node.getClientRects().length)
      const first=controls[0],last=controls.at(-1)
      if(event.shiftKey && document.activeElement===first) {event.preventDefault();last?.focus()}
      else if(!event.shiftKey && document.activeElement===last) {event.preventDefault();first?.focus()}
    }}>
    <header className="monolith-chat-header"><div><h2 id="monolith-chat-title">{words.title}</h2><p id="monolith-chat-mode">{words.mode}</p></div>
      <div><button onClick={toggleLang} aria-label={words.switchLanguage}>{lang.toUpperCase()}</button><button onClick={close} aria-label={words.close}>×</button></div>
    </header>
    <div className="monolith-chat-body" role="log" aria-label={words.history} aria-live="polite" aria-relevant="additions">
      <div className="chat-message chat-assistant"><p>{words.welcome}</p></div>
      {!messages.length && <div className="chat-suggestions">{words.suggestions.map(question=><button key={question} onClick={()=>send(question)} disabled={loading}>{question}</button>)}</div>}
      {messages.map((message,index)=><section key={index} className={`chat-message chat-${message.role}${message.error?' chat-error':''}`}>
        <span className="chat-speaker">{message.role==='user'?words.you:words.assistant}</span><p>{message.text}</p>
        {message.products?.length>0 && <>
          <p className="chat-checked">{words.now}: {new Date(message.checked_at).toLocaleTimeString(lang==='en'?'en-US':'es-PE')} · {words.total}: {message.count}</p>
          {message.intent==='compare' && <div className="chat-comparison" tabIndex={0} role="region" aria-label={words.compare}>
            <table><caption>{words.compare}</caption><thead><tr><th>{words.results}</th>{message.products.map(p=><th key={p.id}>{getTranslatedText(t, p.nombre)}</th>)}</tr></thead>
              <tbody>{[[words.price,p=>`S/ ${p.precio}`],[words.stock,p=>p.stock],[words.platforms,p=>p.plataformas.map(x=>x.nombre).join(', ')],[words.category,p=>getTranslatedCategory(t,p.categoria) || '—'],[words.rating,p=>p.valoracion ?? '—']].map(([label,value])=><tr key={label}><th>{label}</th>{message.products.map(p=><td key={p.id}>{value(p)}</td>)}</tr>)}</tbody>
            </table></div>}
          <div className="chat-products">{message.products.map(product=><article className="chat-product" key={product.id}>
            <h3>{getTranslatedText(t, product.nombre)}</h3><p><strong>S/ {product.precio}</strong>{product.tiene_descuento && <><del>S/ {product.precio_original}</del><span>−{product.porcentaje_descuento}%</span></>}</p>
            <p>{words.stock}: {product.stock} · {product.disponible?words.available:words.unavailable}</p>
            <p>{product.plataformas.map(p=>p.nombre).join(' · ')}</p>
            <div><button onClick={()=>navigate('detail',{productId:product.id})}>{words.view}</button><button disabled={!product.disponible || loading || adding} onClick={()=>askAdd(product)}>{words.add}</button></div>
            <label><input type="checkbox" checked={selected.includes(product.id)} disabled={!selected.includes(product.id) && selected.length>=3} onChange={()=>setSelected(ids=>ids.includes(product.id)?ids.filter(id=>id!==product.id):[...ids,product.id])} />{words.selectCompare} {getTranslatedText(t, product.nombre)}</label>
          </article>)}</div>
        </>}
        {message.orders?.map(order=><article key={order.id} className="chat-order"><h3>{order.numero}</h3>
          <p>{words.orderStatus}: {getTranslatedOrderStatus(t,order.estado)}</p><p>{words.orderTotal}: S/ {order.monto_total}</p>
          <p>{words.delivery}: {formatDate(order.fecha_estimada_entrega, t)}</p><button onClick={()=>navigate('detallePedido',{orderId:order.id})}>{words.orderDetail}</button></article>)}
        {message.actions?.length>0 && <div className="chat-actions">{message.actions.filter(a=>words.action[a.page]).map((entry,i)=><button key={i} onClick={()=>action(entry)}>{words.action[entry.page]}</button>)}</div>}
        {message.error && message.retry && <button onClick={()=>send(message.retry.message,message.retry.compareIds)} disabled={loading}>{words.retry}</button>}
      </section>)}
      {loading && <p className="chat-working" role="status">{words.loading}</p>}
      <div ref={end} />
    </div>
    {selected.length>=2 && <div className="chat-compare-bar"><button disabled={loading || adding} onClick={()=>send(words.compareCommand,selected)}>{words.compare} ({selected.length}/3)</button></div>}
    {pending && <section className="chat-confirm" aria-label={words.confirm}><h3>{words.confirm}</h3><p>{getTranslatedText(t, pending.nombre)}</p><p>{words.recheck}</p>
      <button autoFocus onClick={confirmAdd} disabled={adding || loading}>{words.confirmYes}</button><button onClick={()=>setPending(null)} disabled={adding}>{words.cancel}</button></section>}
    {notice && <p className="chat-notice" role="status">{getTranslatedText(t, notice)}</p>}
    <form className="monolith-chat-form" onSubmit={event=>{event.preventDefault();send()}}>
      <label htmlFor="monolith-chat-input">{words.input}</label><div><textarea ref={inputRef} id="monolith-chat-input" value={input} maxLength={500} rows={2} onChange={e=>setInput(e.target.value)}
        onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {e.preventDefault();send()}}} /><button type="submit" disabled={loading || adding || !input.trim()}>{words.send}</button></div>
      <small>{input.length}/500 · {words.next}</small><button type="button" className="chat-clear" onClick={clear}>{words.clear}</button>
    </form>
  </dialog>
}
