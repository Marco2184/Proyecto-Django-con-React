import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function Register({ t, onNavigate, onAuth, lang, toggleLang }) {
  const [form, setForm] = useState({ nombre: '', email: '', telefono: '', password1: '', password2: '' })
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setError(''); setMsg(''); setLoading(true)
    try {
      const { data } = await api.post('/auth/register/', form)
      setMsg(data.message)
      onAuth(data.token, data.user)
    } catch (err) { setError(getApiError(err)) }
    finally { setLoading(false) }
  }

  return (
    <div className="auth-split">
      <section className="auth-hero"><div className="mono-line">// MONOLITH //</div><h1>CREATE<br/><span>YOUR<br/>ARSENAL</span></h1><div className="hero-sep"/><p>Registro con verificación de correo usando Django.</p><div className="terminal-box">&gt; REGISTER MODULE<br/>&gt; SMTP READY<br/>&gt; _</div><div className="lang-switch"><button className={lang === 'es' ? 'active' : ''} onClick={toggleLang}>ES</button><button className={lang === 'en' ? 'active' : ''} onClick={toggleLang}>EN</button></div></section>
      <section className="auth-panel">
        <div className="section-tag">Autenticación // Registro</div><h2>{t.register.toUpperCase()}</h2>
        {error && <div className="alert error">{error}</div>}{msg && <div className="alert success">{msg}</div>}
        <form onSubmit={submit} className="form-stack">
          <label>{t.name}</label><input className="input-m" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} required />
          <label>{t.email}</label><input className="input-m" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
          <label>{t.phone}</label><input className="input-m" value={form.telefono} onChange={e => setForm({ ...form, telefono: e.target.value })} />
          <label>{t.password}</label><input className="input-m" type="password" value={form.password1} onChange={e => setForm({ ...form, password1: e.target.value })} required />
          <label>{t.confirm}</label><input className="input-m" type="password" value={form.password2} onChange={e => setForm({ ...form, password2: e.target.value })} required />
          <button className="btn-neon w-100" disabled={loading}>{loading ? '...' : t.create}</button>
        </form>
        <div className="auth-foot">{t.haveAccount} <button className="link-neon" onClick={() => onNavigate('login')}>{t.login}</button></div>
      </section>
    </div>
  )
}
