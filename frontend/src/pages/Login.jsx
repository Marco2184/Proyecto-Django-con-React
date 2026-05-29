import { useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'

export default function Login({ t, onNavigate, onAuth, lang, toggleLang }) {
  const [form, setForm] = useState({
    email: '',
    password: '',
    remember_me: true
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const heroLines = useMemo(() => {
    const title = t.loginHeroTitle || ''

    if (lang === 'es') {
      return ['ASCIENDE', 'AL', 'VERDADERO', 'PODER']
    }

    if (lang === 'en') {
      return ['ASCEND', 'TO', 'TRUE', 'POWER']
    }

    return title.toUpperCase().split(' ')
  }, [lang, t.loginHeroTitle])

  const submit = async (event) => {
    event.preventDefault()

    setLoading(true)
    setError('')

    try {
      const { data } = await api.post('/auth/login/', form)
      onAuth(data.token, data.user)
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
          {heroLines[0]}
          <br />
          {heroLines[1]}
          <br />
          <span>
            {heroLines[2]}
            <br />
            {heroLines[3]}
          </span>
        </h1>

        <div className="hero-sep" />

        <p>
          {t.loginHeroSubtitle}
        </p>

        <div className="terminal-box">
          &gt; {t.systemOnline}
          <br />
          &gt; {t.awaitingAuthentication}
          <br />
          &gt; _
        </div>

        <div className="lang-switch">
          <button
            className={lang === 'es' ? 'active' : ''}
            onClick={toggleLang}
          >
            ES
          </button>

          <button
            className={lang === 'en' ? 'active' : ''}
            onClick={toggleLang}
          >
            EN
          </button>
        </div>
      </section>

      <section className="auth-panel">
        <div className="section-tag">{t.loginTag}</div>
        <h2>{t.loginTitle}</h2>
        <p className="muted">{t.loginSubtitle}</p>

        {error && <div className="alert error">{error}</div>}

        <form onSubmit={submit} className="form-stack">
          <label>{t.email}</label>
          <input
            className="input-m"
            value={form.email}
            onChange={(event) =>
              setForm({
                ...form,
                email: event.target.value
              })
            }
            placeholder={t.emailPlaceholder}
            type="email"
            required
          />

          <label>{t.password}</label>
          <input
            className="input-m"
            value={form.password}
            onChange={(event) =>
              setForm({
                ...form,
                password: event.target.value
              })
            }
            placeholder={t.password}
            type="password"
            required
          />

          <div className="row-between">
            <label className="check-line">
              <input
                type="checkbox"
                checked={form.remember_me}
                onChange={(event) =>
                  setForm({
                    ...form,
                    remember_me: event.target.checked
                  })
                }
              />
              {t.remember}
            </label>

            <button
              type="button"
              className="link-neon"
              onClick={() => onNavigate('forgot')}
            >
              {t.forgot}
            </button>
          </div>

          <button className="btn-neon w-100" disabled={loading}>
            {loading ? '...' : t.signIn}
          </button>
        </form>

        <div className="auth-foot">
          {t.newHere}{' '}
          <button
            className="link-neon"
            onClick={() => onNavigate('register')}
          >
            {t.create}
          </button>
        </div>
      </section>
    </div>
  )
}