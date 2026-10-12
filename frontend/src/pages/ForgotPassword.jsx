import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function ForgotPassword({ t, onNavigate }) {
  const [email, setEmail] = useState('')
  const [msgKey, setMsgKey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setMsgKey('')
    setError('')
    setLoading(true)

    try {
      await api.post('/auth/forgot-password/', {email})
      setMsgKey('passwordResetEmailSent')
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel-page narrow">
      <div className="section-tag">{t.forgotTag}</div>
      <h1>{t.forgotTitle}</h1>

      {msgKey && <div className="alert success">{t[msgKey]}</div>}
      {error && <div className="alert error">{error}</div>}

      <form className="form-stack" onSubmit={submit}>
        <label>{t.email}</label>
        <input
          className="input-m"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <button className="btn-neon" disabled={loading}>
          {loading ? t.sending : t.sendLink}
        </button>

        <button type="button" className="btn-ghost" onClick={() => onNavigate('login')}>
          {t.back}
        </button>
      </form>
    </div>
  )
}
