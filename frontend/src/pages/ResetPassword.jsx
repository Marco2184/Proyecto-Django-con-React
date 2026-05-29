import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function ResetPassword({ t, token, onNavigate }) {
  const [form, setForm] = useState({ password1: '', password2: '' })
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const submit = async e => {
    e.preventDefault(); setMsg(''); setError('')
    try { const { data } = await api.post(`/auth/reset-password/${token}/`, form); setMsg(data.message) }
    catch (err) { setError(getApiError(err)) }
  }
  return <div className="panel-page narrow"><div className="section-tag">Password // Reset</div><h1>NUEVA CONTRASEÑA</h1>{msg && <div className="alert success">{msg}</div>}{error && <div className="alert error">{error}</div>}<form className="form-stack" onSubmit={submit}><label>{t.password}</label><input className="input-m" type="password" value={form.password1} onChange={e=>setForm({...form,password1:e.target.value})} required/><label>{t.confirm}</label><input className="input-m" type="password" value={form.password2} onChange={e=>setForm({...form,password2:e.target.value})} required/><button className="btn-neon">Actualizar</button><button type="button" className="btn-ghost" onClick={()=>onNavigate('login')}>Login</button></form></div>
}
