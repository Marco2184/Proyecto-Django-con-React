import { useEffect, useRef, useState } from 'react'
import AppLink from './AppLink'

export default function Navbar({ user, onLogout, cartItems, onNavigate, page, lang, toggleLang, t }) {
  const initials = user?.nombre ? user.nombre.slice(0, 2).toUpperCase() : '??'
  const [confirmLogout, setConfirmLogout] = useState(false)
  const dialogRef = useRef(null)
  useEffect(() => {if (confirmLogout) dialogRef.current?.showModal()}, [confirmLogout])

  const doLogout = async () => {
    setConfirmLogout(false)
    await onLogout()
  }

  return (
    <>
      <nav className="nav-monolith">
        <AppLink className="nav-brand brand-text-only" page="catalog" onNavigate={onNavigate}>MONOLITH</AppLink>

        <div className="nav-links">
          {[['catalog',t.catalog],['cart',`${t.cart}${cartItems>0 ? ` (${cartItems})` : ''}`],...(user ? [['wishlist',t.wishlist],['misPedidos',t.myOrders],['profile',t.profile]] : []),...(user?.is_staff ? [['admin','Admin']] : [])].map(([target,label]) =>
            <AppLink key={target} className={`nav-link-m ${page===target ? 'active' : ''}`} page={target} onNavigate={onNavigate} aria-current={page===target ? 'page' : undefined}>{label}</AppLink>)}
        </div>

        <div className="nav-right">
          <button className="lang-pill" onClick={toggleLang} aria-label={t.changeLanguage}>{lang.toUpperCase()}</button>
          {user ? (
            <>
              <AppLink className="nav-user-pill" page="profile" onNavigate={onNavigate}>
                <div className="nav-avatar">{initials}</div>
                <span className="nav-username">{user.nombre?.split(' ')[0] || user.email}</span>
                {!user.email_verificado && <span className="verify-dot">!</span>}
              </AppLink>
              <button className="btn-logout-m" onClick={() => setConfirmLogout(true)}>{t.logout}</button>
            </>
          ) : <button className="btn-nav-login" onClick={() => onNavigate('login')}>{t.login}</button>}
        </div>
      </nav>

      {confirmLogout && (
        <dialog ref={dialogRef} className="confirm-modal" aria-labelledby="logout-title" onCancel={() => setConfirmLogout(false)}>
            <div className="section-tag">{t.sessionSecurity}</div>
            <h2 id="logout-title">{t.logoutTitle}</h2>
            <p className="muted">{t.logoutText}</p>
            <div className="row-actions">
              <button className="btn-ghost" autoFocus onClick={() => setConfirmLogout(false)}>{t.cancel}</button>
              <button className="btn-neon" onClick={doLogout}>{t.yesLogout}</button>
            </div>
        </dialog>
      )}
    </>
  )
}
