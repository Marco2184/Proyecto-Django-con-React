import {useState} from 'react'
import {getTranslatedOrderStatus} from '../i18n'

function Chart({rows,label,t}) {
  const max=Math.max(1,...rows.map(r=>Number(r.value))),width=640,height=180
  if(!rows.length)return <div className="empty-state">{t.noSales}</div>
  const points=rows.map((r,i)=>`${30+(i*(width-60)/Math.max(1,rows.length-1))},${height-25-Number(r.value)/max*(height-50)}`).join(' ')
  return <><svg className="sales-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}><title>{label}</title><defs><linearGradient id={`chart-${label.replace(/\W/g,'')}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#00ff41" stopOpacity=".35"/><stop offset="1" stopColor="#00ff41" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75,1].map(n=><line key={n} x1="25" x2="625" y1={height-25-n*(height-50)} y2={height-25-n*(height-50)} stroke="#28432e" strokeDasharray="4 4"/>)}<polygon points={`30,${height-25} ${points} ${width-30},${height-25}`} fill={`url(#chart-${label.replace(/\W/g,'')})`}/><polyline points={points} fill="none" stroke="#00ff41" strokeWidth="3"/>{rows.map((r,i)=><circle key={r.label} cx={30+i*(width-60)/Math.max(1,rows.length-1)} cy={height-25-Number(r.value)/max*(height-50)} r="4" fill="#00ff41"><title>{r.label}: {r.value}</title></circle>)}</svg><details><summary>{t.viewData}</summary><div className="admin-table-wrap"><table className="admin-table"><caption>{label}</caption><thead><tr><th>{t.period}</th><th>{t.amount}</th></tr></thead><tbody>{rows.map(r=><tr key={r.label}><td>{r.label}</td><td>{r.value}</td></tr>)}</tbody></table></div></details></>
}

export default function AdminAnalytics({data,t,desde,hasta,onDates}) {
  const [period,setPeriod]=useState('daily'),[start,setStart]=useState(desde||''),[end,setEnd]=useState(hasta||'')
  if(!data)return null
  const rows=(data.series?.[period]||[]).map(r=>({label:r.fecha,value:r.ingresos}))
  const money=v=>`S/ ${Number(v||0).toLocaleString(document.documentElement.lang==='en'?'en-US':'es-PE',{minimumFractionDigits:2,maximumFractionDigits:2})}`
  return <section className="panel-card analytics-panel"><h2>{t.salesAnalytics}</h2><form className="date-filters" onSubmit={e=>{e.preventDefault();onDates(start,end)}}><label>{t.dateFrom}<input type="date" className="input-m" required value={start} onChange={e=>setStart(e.target.value)}/></label><label>{t.dateTo}<input type="date" className="input-m" required min={start||undefined} value={end} onChange={e=>setEnd(e.target.value)}/></label><button className="btn-neon">{t.applyFilters}</button></form><p className="muted">{data.desde} — {data.hasta}</p>
    <div className="analytics-kpis"><div><span>{t.periodRevenue}</span><strong>{money(data.comparacion?.actual)}</strong></div><div><span>{t.previousPeriod}</span><strong>{money(data.comparacion?.anterior)}</strong></div><div><span>{t.change}</span><strong>{data.comparacion?.porcentaje==null?t.noPreviousPeriod:`${data.comparacion.porcentaje}%`}</strong></div><div><span>{t.registeredClients}</span><strong>{data.clientes_total}</strong></div><div><span>{t.outStock}</span><strong>{data.agotados_total}</strong></div></div>
    <label>{t.groupBy}<select className="input-m" value={period} onChange={e=>setPeriod(e.target.value)}>{['daily','weekly','monthly'].map(p=><option key={p} value={p}>{t[p]}</option>)}</select></label><Chart rows={rows} label={t.revenue} t={t}/>
    <div className="analytics-columns"><section><h3>{t.ordersByStatus}</h3>{Object.keys(data.estados_periodo||{}).length?Object.entries(data.estados_periodo).map(([state,count])=><div className="metric-bar" key={state}><span>{getTranslatedOrderStatus(t,state)}</span><meter aria-label={getTranslatedOrderStatus(t,state)} min="0" max={Math.max(1,...Object.values(data.estados_periodo))} value={count}/><strong>{count}</strong></div>):<p>{t.noSales}</p>}</section><section><h3>{t.bestSellers}</h3>{data.top_productos?.length?<ol>{data.top_productos.map(p=><li key={p.producto_id}>{p.producto__nombre} <strong>×{p.cantidad}</strong></li>)}</ol>:<p>{t.noSales}</p>}</section></div>
  </section>
}
