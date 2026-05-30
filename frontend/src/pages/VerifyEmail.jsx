export default function VerifyEmail({ t, onNavigate }) {
  return (
    <div className="panel-page narrow">
      <div className="section-tag">{t.verifyTag}</div>
      <h1>{t.verifyTitle}</h1>

      <div className="alert success">{t.firebaseVerificationInfo}</div>

      <button className="btn-neon" onClick={() => onNavigate('login')}>
        {t.goToLogin}
      </button>
    </div>
  )
}
