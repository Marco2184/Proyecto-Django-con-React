import { useState } from 'react'
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
    setForm({
      ...form,
      [field]: value
    })
  }

  const submit = async (event) => {
    event.preventDefault()

    setError('')
    setMsg('')
    setLoading(true)

    try {
      const { data } = await api.post('/auth/register/', form)

      setMsg(
        data.message ||
          data.detail ||
          t.verifyMail ||
          'Cuenta creada. Revisa tu correo para verificarla.'
      )

      setForm({
        nombre: '',
        email: '',
        telefono: '',
        password1: '',
        password2: ''
      })
    } catch (err) {
      setError(getApiError(err))
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
            <>
              CREA
              <br />
              TU
              <br />
              <span>
                ARSENAL
                <br />
                GAMER
              </span>
            </>
          ) : (
            <>
              CREATE
              <br />
              YOUR
              <br />
              <span>
                GAMING
                <br />
                ARSENAL
              </span>
            </>
          )}
        </h1>

        <div className="hero-sep" />

        <p>{t.registerHeroSubtitle}</p>

        <div className="terminal-box">
          &gt; {t.registerModule}
          <br />
          &gt; {t.smtpReady}
          <br />
          &gt; _
        </div>

        <div className="lang-switch">
          <button
            className={lang === 'es' ? 'active' : ''}
            onClick={toggleLang}
            type="button"
          >
            ES
          </button>

          <button
            className={lang === 'en' ? 'active' : ''}
            onClick={toggleLang}
            type="button"
          >
            EN
          </button>
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
          <input
            className="input-m"
            value={form.nombre}
            onChange={(event) => handleChange('nombre', event.target.value)}
            placeholder={t.name}
            required
          />

          <label>{t.email}</label>
          <input
            className="input-m"
            value={form.email}
            onChange={(event) => handleChange('email', event.target.value)}
            placeholder="correo@ejemplo.com"
            type="email"
            required
          />

          <label>{t.phone}</label>
          <input
            className="input-m"
            value={form.telefono}
            onChange={(event) => handleChange('telefono', event.target.value)}
            placeholder={t.phone}
          />

          <label>{t.password}</label>
          <input
            className="input-m"
            value={form.password1}
            onChange={(event) => handleChange('password1', event.target.value)}
            placeholder={t.password}
            type="password"
            required
          />

          <label>{t.confirm}</label>
          <input
            className="input-m"
            value={form.password2}
            onChange={(event) => handleChange('password2', event.target.value)}
            placeholder={t.confirm}
            type="password"
            required
          />

          <button className="btn-neon w-100" disabled={loading}>
            {loading ? '...' : t.create}
          </button>
        </form>

        <div className="auth-foot">
          {t.haveAccount}{' '}
          <button
            className="link-neon"
            onClick={() => onNavigate('login')}
            type="button"
          >
            {t.login}
          </button>
        </div>
      </section>
    </div>
  )
}