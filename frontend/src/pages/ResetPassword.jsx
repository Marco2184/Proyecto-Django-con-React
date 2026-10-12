import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function ResetPassword({ t, token, onNavigate }) {
  const [form, setForm] = useState({ password1: '', password2: '' })
  const [msgKey, setMsgKey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setMsgKey('')
    setError('')

    if (form.password1 !== form.password2) {
      setError(t.passwordsDontMatch)
      return
    }

    setLoading(true)

    try {
      await api.post(`/auth/reset-password/${token}/`, form)
      setMsgKey('passwordResetDone')
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel-page narrow">
      <div className="section-tag">{t.resetTag}</div>
      <h1>{t.resetTitle}</h1>

      {msgKey && <div className="alert success">{t[msgKey]}</div>}
      {error && <div className="alert error">{error}</div>}

      <form className="form-stack" onSubmit={submit}>
        <label>{t.password}</label>
        <input
          className="input-m"
          type="password"
          value={form.password1}
          onChange={(event) => setForm({ ...form, password1: event.target.value })}
          required
          minLength={6}
        />

        <label>{t.confirm}</label>
        <input
          className="input-m"
          type="password"
          value={form.password2}
          onChange={(event) => setForm({ ...form, password2: event.target.value })}
          required
          minLength={6}
        />

        <button className="btn-neon" disabled={loading}>
          {loading ? t.updating : t.update}
        </button>

        <button type="button" className="btn-ghost" onClick={() => onNavigate('login')}>
          {t.login}
        </button>
      </form>
    </div>
  )
}
