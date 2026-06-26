import { useState } from 'react'

export default function Navbar({ user, onLogout, cartItems, onNavigate, page, lang, toggleLang, t }) {
  const initials = user?.nombre ? user.nombre.slice(0, 2).toUpperCase() : '??'
  const [confirmLogout, setConfirmLogout] = useState(false)

  const doLogout = async () => {
    setConfirmLogout(false)
    await onLogout()
  }

  return (
    <>
      <nav className="nav-monolith">
        <div className="nav-brand brand-text-only" onClick={() => onNavigate('catalog')}>MONOLITH</div>

        <div className="nav-links">
          <span className={`nav-link-m ${page === 'catalog' ? 'active' : ''}`} onClick={() => onNavigate('catalog')}>{t.catalog}</span>
          <span className={`nav-link-m ${page === 'cart' ? 'active' : ''}`} onClick={() => user ? onNavigate('cart') : onNavigate('login')}>{t.cart} {cartItems > 0 && `(${cartItems})`}</span>
          {user && <span className={`nav-link-m ${page === 'misPedidos' || page === 'detallePedido' ? 'active' : ''}`} onClick={() => onNavigate('misPedidos')}>{t.myOrders || 'Mis pedidos'}</span>}
          {user && <span className={`nav-link-m ${page === 'profile' ? 'active' : ''}`} onClick={() => onNavigate('profile')}>{t.profile}</span>}
          {user?.is_staff && <span className={`nav-link-m ${page === 'admin' ? 'active' : ''}`} onClick={() => onNavigate('admin')}>Admin</span>}
        </div>

        <div className="nav-right">
          <button className="lang-pill" onClick={toggleLang}>{lang.toUpperCase()}</button>
          {user ? (
            <>
              <div className="nav-user-pill" onClick={() => onNavigate('profile')}>
                <div className="nav-avatar">{initials}</div>
                <span className="nav-username">{user.nombre?.split(' ')[0] || user.email}</span>
                {!user.email_verificado && <span className="verify-dot">!</span>}
              </div>
              <button className="btn-logout-m" onClick={() => setConfirmLogout(true)}>{t.logout}</button>
            </>
          ) : <button className="btn-nav-login" onClick={() => onNavigate('login')}>{t.login}</button>}
        </div>
      </nav>

      {confirmLogout && (
        <div className="confirm-backdrop" role="dialog" aria-modal="true">
          <div className="confirm-modal">
            <div className="section-tag">{t.sessionSecurity}</div>
            <h2>{t.logoutTitle}</h2>
            <p className="muted">{t.logoutText}</p>
            <div className="row-actions">
              <button className="btn-ghost" onClick={() => setConfirmLogout(false)}>{t.cancel}</button>
              <button className="btn-neon" onClick={doLogout}>{t.yesLogout}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
