import { getTranslatedText } from '../i18n'
import { useRef, useState } from 'react'
import { authApi, getApiError } from '../services/api'

export default function Register({ t, onNavigate, onAuth, lang, toggleLang }) {
  const requestId = useRef(sessionStorage.getItem('monolith-registration')||crypto.randomUUID())
  const submitting = useRef(false)
  const [form, setForm] = useState({
    nombre: '',
    email: '',
    telefono: '',
    password1: '',
    password2: ''
  })

  const [error, setError] = useState('')
  const [msgKey, setMsgKey] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value })
  }

  const submit = async (event) => {
    event.preventDefault()
    if (submitting.current) return
    setError('')
    setMsgKey('')
    setLoading(true)

    if (form.password1 !== form.password2) {
      setError(t.passwordsDontMatch)
      setLoading(false)
      return
    }

    try {
      submitting.current = true
      sessionStorage.setItem('monolith-registration',requestId.current)
      const {data} = await authApi.post('/auth/register', form, {headers:{'Idempotency-Key':requestId.current}, timeout:30000})
      setForm({ nombre: '', email: '', telefono: '', password1: '', password2: '' })
      sessionStorage.removeItem('monolith-registration')
      onAuth(data.access, data.user)
    } catch (err) {
      if (err.code === 'auth/email-already-in-use') {
        setError(t.emailAlreadyInUse)
      } else if (err.code === 'auth/weak-password') {
        setError(t.weakPassword)
      } else {
        setError(getApiError(err))
      }
    } finally {
      submitting.current = false
      setLoading(false)
    }
  }

  return (
    <div className="auth-split">
      <section className="auth-hero">
        <div className="mono-line">// {t.appName} //</div>
        <h1>
          {lang === 'es' ? (
            <>CREA<br />TU<br /><span>ARSENAL<br />GAMER</span></>
          ) : (
            <>CREATE<br />YOUR<br /><span>GAMING<br />ARSENAL</span></>
          )}
        </h1>
        <div className="hero-sep" />
        <p>{t.registerHeroSubtitle}</p>
        <div className="terminal-box">
          &gt; {t.registerModule}<br />
          &gt; Monolith Auth<br />
          &gt; _
        </div>
        <div className="lang-switch">
          <button className={lang === 'es' ? 'active' : ''} onClick={() => { if (lang !== 'es') toggleLang() }} type="button">ES</button>
          <button className={lang === 'en' ? 'active' : ''} onClick={() => { if (lang !== 'en') toggleLang() }} type="button">EN</button>
        </div>
      </section>

      <section className="auth-panel">
        <div className="section-tag">{t.registerTag}</div>
        <h2>{t.register}</h2>
        <p className="muted">{t.registerHeroSubtitle}</p>

        {msgKey && <div className="alert success">{t[msgKey]}</div>}
        {error && <div className="alert error" role="alert">{getTranslatedText(t, error)}<p>{t.retryRegistration}</p></div>}

        <form onSubmit={submit} className="form-stack">
          <label htmlFor="register-nombre">{t.name}</label>
          <input id="register-nombre" className="input-m" value={form.nombre} onChange={(e) => handleChange('nombre', e.target.value)} placeholder={t.name} required />

          <label htmlFor="register-email">{t.email}</label>
          <input id="register-email" className="input-m" value={form.email} onChange={(e) => handleChange('email', e.target.value)} placeholder={t.emailExample} type="email" required />

          <label htmlFor="register-telefono">{t.phone}</label>
          <input id="register-telefono" className="input-m" value={form.telefono} onChange={(e) => handleChange('telefono', e.target.value)} placeholder={t.phone} />

          <label htmlFor="register-password1">{t.password}</label>
          <input id="register-password1" className="input-m" value={form.password1} onChange={(e) => handleChange('password1', e.target.value)} placeholder={t.password} type="password" required />

          <label htmlFor="register-password2">{t.confirm}</label>
          <input id="register-password2" className="input-m" value={form.password2} onChange={(e) => handleChange('password2', e.target.value)} placeholder={t.confirm} type="password" required />

          <button className="btn-neon w-100" disabled={loading}>
            {loading ? '...' : t.create}
          </button>
        </form>

        <div className="auth-foot">
          {t.haveAccount}{' '}
          <button className="link-neon" onClick={() => onNavigate('login')} type="button">{t.login}</button>
        </div>
      </section>
    </div>
  )
}
