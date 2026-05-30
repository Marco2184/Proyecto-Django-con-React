import { useMemo, useState } from 'react'
import { auth } from '../services/firebase'
import { signInWithEmailAndPassword } from 'firebase/auth'
import { api, getApiError } from '../services/api'

export default function Login({ t, onNavigate, onAuth, lang, toggleLang }) {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const heroLines = useMemo(() => {
    if (lang === 'es') return ['ASCIENDE', 'AL', 'VERDADERO', 'PODER']
    return ['ASCEND', 'TO', 'TRUE', 'POWER']
  }, [lang])

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      // 1. Login con Firebase
      const { user } = await signInWithEmailAndPassword(auth, form.email, form.password)

      // 2. Obtener token de Firebase
      const token = await user.getIdToken()

      // 3. Enviar token a Django para obtener token DRF
      const { data } = await api.post('/auth/firebase-login/', {}, {
        headers: { Authorization: `Firebase ${token}` }
      })

      onAuth(data.token, data.user)
    } catch (err) {
      if (err.code === 'auth/invalid-credential' || err.code === 'auth/wrong-password') {
        setError('Correo o contraseña incorrectos.')
      } else if (err.code === 'auth/user-not-found') {
        setError('No existe una cuenta con este correo.')
      } else if (err.code === 'auth/too-many-requests') {
        setError('Demasiados intentos. Intenta más tarde.')
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
          {heroLines[0]}<br />{heroLines[1]}<br />
          <span>{heroLines[2]}<br />{heroLines[3]}</span>
        </h1>
        <div className="hero-sep" />
        <p>{t.loginHeroSubtitle}</p>
        <div className="terminal-box">
          &gt; {t.systemOnline}<br />
          &gt; Firebase Auth<br />
          &gt; _
        </div>
        <div className="lang-switch">
          <button className={lang === 'es' ? 'active' : ''} onClick={toggleLang}>ES</button>
          <button className={lang === 'en' ? 'active' : ''} onClick={toggleLang}>EN</button>
        </div>
      </section>

      <section className="auth-panel">
        <div className="section-tag">{t.loginTag}</div>
        <h2>{t.loginTitle}</h2>
        <p className="muted">{t.loginSubtitle}</p>

        {error && <div className="alert error">{error}</div>}

        <form onSubmit={submit} className="form-stack">
          <label>{t.email}</label>
          <input className="input-m" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder={t.emailPlaceholder} type="email" required />

          <label>{t.password}</label>
          <input className="input-m" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={t.password} type="password" required />

          <div className="row-between">
            <button type="button" className="link-neon" onClick={() => onNavigate('forgot')}>{t.forgot}</button>
          </div>

          <button className="btn-neon w-100" disabled={loading}>
            {loading ? '...' : t.signIn}
          </button>
        </form>

        <div className="auth-foot">
          {t.newHere}{' '}
          <button className="link-neon" onClick={() => onNavigate('register')}>{t.create}</button>
        </div>
      </section>
    </div>
  )
}