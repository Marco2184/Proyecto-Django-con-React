import { useState } from 'react'
import { auth } from '../services/firebase'
import { createUserWithEmailAndPassword, sendEmailVerification, updateProfile } from 'firebase/auth'
import { api, getApiError } from '../services/api'

export default function Register({ t, onNavigate, lang, toggleLang }) {
  const [form, setForm] = useState({
    nombre: '',
    email: '',
    telefono: '',
    password1: '',
    password2: ''
  })

  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value })
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setMsg('')
    setLoading(true)

    if (form.password1 !== form.password2) {
      setError('Las contraseñas no coinciden.')
      setLoading(false)
      return
    }

    try {
      // 1. Crear usuario en Firebase
      const { user } = await createUserWithEmailAndPassword(auth, form.email, form.password1)

      // 2. Actualizar nombre en Firebase
      await updateProfile(user, { displayName: form.nombre })

      // 3. Enviar verificación de correo desde Firebase
      await sendEmailVerification(user)

      // 4. Registrar datos adicionales en Django
      const token = await user.getIdToken()
      await api.post('/auth/firebase-register/', {
        nombre: form.nombre,
        email: form.email,
        telefono: form.telefono,
        firebase_uid: user.uid
      }, {
        headers: { Authorization: `Firebase ${token}` }
      })

      setMsg('Cuenta creada. Revisa tu correo para verificarla.')
      setForm({ nombre: '', email: '', telefono: '', password1: '', password2: '' })
    } catch (err) {
      if (err.code === 'auth/email-already-in-use') {
        setError('Este correo ya está registrado.')
      } else if (err.code === 'auth/weak-password') {
        setError('La contraseña debe tener al menos 6 caracteres.')
      } else {
        setError(err.message || getApiError(err))
      }
    } finally {
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
          &gt; Firebase Auth<br />
          &gt; _
        </div>
        <div className="lang-switch">
          <button className={lang === 'es' ? 'active' : ''} onClick={toggleLang} type="button">ES</button>
          <button className={lang === 'en' ? 'active' : ''} onClick={toggleLang} type="button">EN</button>
        </div>
      </section>

      <section className="auth-panel">
        <div className="section-tag">{t.registerTag}</div>
        <h2>{t.register}</h2>
        <p className="muted">{t.registerHeroSubtitle}</p>

        {msg && <div className="alert success">{msg}</div>}
        {error && <div className="alert error">{error}</div>}

        <form onSubmit={submit} className="form-stack">
          <label>{t.name}</label>
          <input className="input-m" value={form.nombre} onChange={(e) => handleChange('nombre', e.target.value)} placeholder={t.name} required />

          <label>{t.email}</label>
          <input className="input-m" value={form.email} onChange={(e) => handleChange('email', e.target.value)} placeholder="correo@ejemplo.com" type="email" required />

          <label>{t.phone}</label>
          <input className="input-m" value={form.telefono} onChange={(e) => handleChange('telefono', e.target.value)} placeholder={t.phone} />

          <label>{t.password}</label>
          <input className="input-m" value={form.password1} onChange={(e) => handleChange('password1', e.target.value)} placeholder={t.password} type="password" required />

          <label>{t.confirm}</label>
          <input className="input-m" value={form.password2} onChange={(e) => handleChange('password2', e.target.value)} placeholder={t.confirm} type="password" required />

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