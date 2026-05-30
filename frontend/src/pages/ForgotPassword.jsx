import { useState } from 'react'
import { sendPasswordResetEmail } from 'firebase/auth'
import { auth } from '../services/firebase'
import { getTranslatedText } from '../i18n'

export default function ForgotPassword({ t, onNavigate }) {
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setMsg('')
    setError('')
    setLoading(true)

    try {
      await sendPasswordResetEmail(auth, email)
      setMsg(t.passwordResetEmailSent)
    } catch (err) {
      setError(getTranslatedText(t, err.code || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel-page narrow">
      <div className="section-tag">{t.forgotTag}</div>
      <h1>{t.forgotTitle}</h1>

      {msg && <div className="alert success">{msg}</div>}
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
