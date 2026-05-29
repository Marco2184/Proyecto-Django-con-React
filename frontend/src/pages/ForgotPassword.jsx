import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function ForgotPassword({ t, onNavigate }) {
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const submit = async e => {
    e.preventDefault(); setMsg(''); setError('')
    try { const { data } = await api.post('/auth/forgot-password/', { email }); setMsg(data.message) }
    catch (err) { setError(getApiError(err)) }
  }
  return <div className="panel-page narrow"><div className="section-tag">Password // Recovery</div><h1>RECUPERAR ACCESO</h1>{msg && <div className="alert success">{msg}</div>}{error && <div className="alert error">{error}</div>}<form className="form-stack" onSubmit={submit}><label>{t.email}</label><input className="input-m" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/><button className="btn-neon">Enviar enlace</button><button type="button" className="btn-ghost" onClick={()=>onNavigate('login')}>Volver</button></form></div>
}
