import WishlistNotice from './components/WishlistNotice'
import ScreenBoundary from './components/ScreenBoundary'
import { useEffect, useMemo, useState, useCallback, lazy, Suspense } from 'react'
import './styles/global.css'
import './styles/app.css'
import './styles/ux.css'
import useLocation from './hooks/useLocation'
import { protectedPages, safeDestination } from './navigation'
import Navbar from './components/Navbar'
import Catalog from './pages/Catalog'
import Login from './pages/Login'
import Register from './pages/Register'
import Cart from './pages/Cart'
import VerifyEmail from './pages/VerifyEmail'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import MisPedidos from './pages/MisPedidos'
import PedidoConfirmado from './pages/PedidoConfirmado'
import { api, authApi, bootstrapAuth, setAuthToken } from './services/api'
import { dict } from './i18n'
import ChatLauncher from './components/ChatLauncher'
import { WishlistProvider } from './components/WishlistContext'
import Wishlist from './pages/Wishlist'
import VerificationNotice from './components/VerificationNotice'

const Profile=lazy(()=>import('./pages/Profile'))
const Checkout=lazy(()=>import('./pages/Checkout'))
const DetallePedido=lazy(()=>import('./pages/DetallePedido'))
const AdminDashboard=lazy(()=>import('./pages/AdminDashboard'))
const ProductDetail=lazy(()=>import('./pages/ProductDetail'))

function App() {
  const { location, navigate, visit, query } = useLocation()
  const { page, token:routeToken, productId, orderId } = location
  const [authReady, setAuthReady] = useState(false)
  const [cartQuantities, setCartQuantities] = useState({})
  const [cartSnapshot,setCartSnapshot] = useState(null)
  const [user, setUser] = useState(null)
  const [firebaseUser, setFirebaseUser] = useState(null)
  const [firebaseReady, setFirebaseReady] = useState(false)
  const [cartCount, setCartCount] = useState(0)
  const [lang, setLang] = useState(localStorage.getItem('lang') === 'en' ? 'en' : 'es')
  const t = useMemo(() => dict[lang], [lang])

  const handleCartChange = useCallback((data) => {
    if (!data) return
    setCartSnapshot(data)
    setCartCount(data.cantidad_items || 0)
    setCartQuantities(Object.fromEntries((data.items || []).map(item => [item.producto.id, item.cantidad])))
  }, [])

  const fetchCartCount = useCallback(async () => {
    try { const {data} = await api.get('/cart/'); handleCartChange(data) }
    catch { setCartCount(0); setCartQuantities({}) }
  }, [handleCartChange])

  useEffect(() => {
    let mounted = true

    const initBackendSession = async () => {
      const nextUser = await bootstrapAuth()
      if (!mounted) return

      if (nextUser) {
        setUser(nextUser)
        if (!['cart','checkout'].includes(page)) fetchCartCount()
      } else {
        setUser(null)
        setCartCount(0)
      }
    }

    initBackendSession().finally(() => { if (mounted) setAuthReady(true) })
    setFirebaseReady(true)

    return () => {
      mounted = false
    }
  }, [fetchCartCount])

  useEffect(() => {
    localStorage.setItem('lang', lang)
    api.post('/i18n/set-language/', { language: lang }).catch(() => {})
  }, [lang])

  useEffect(() => {
    if (authReady && !user && protectedPages.has(page)) {
      navigate('login', {replace:true, next:location.pathname + location.search})
    }
  }, [authReady, user, page, location.pathname, location.search, navigate])

  useEffect(() => {
    document.documentElement.lang = lang
    document.title = `${t[page === 'catalog' ? 'catalog' : page === 'cart' ? 'cart' : page === 'profile' ? 'profile' : 'appName']} | Monolith`
  }, [page, lang, t])

  useEffect(() => {
    if (page==='catalog') sessionStorage.setItem('monolith-catalog-url', location.pathname + location.search)
  }, [page, location.pathname, location.search])

  useEffect(() => {
    document.getElementById('main-content')?.focus({preventScroll:true})
    if (location.navigationType!=='pop') window.scrollTo({top:0, behavior:'instant'})
  }, [location.pathname])

  const handleAuth = (token, nextUser) => {
    setAuthToken(token)
    setUser(nextUser)
    fetchCartCount()
    visit(safeDestination(new URLSearchParams(location.search).get('next')), {replace:true})
  }

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout/')
    } catch {}

    try {
      await authApi.post('/auth/logout')
    } catch {}

    setAuthToken(null)
    setUser(null)
    setFirebaseUser(null)
    setCartCount(0)
    setCartQuantities({})
    setCartSnapshot(null)
    for (const key of Object.keys(sessionStorage)) if (key.startsWith('monolith-draft:')) sessionStorage.removeItem(key)
    navigate('catalog')
  }

  const toggleLang = () => { const next = lang === 'es' ? 'en' : 'es'; localStorage.setItem('lang', next); document.documentElement.lang = next; setLang(next) }

  useEffect(() => {
    const invalid = event => {
      const field = event.target
      if (!field.validity || !field.setCustomValidity) return
      field.setCustomValidity('')
      const validity = field.validity
      field.setCustomValidity(validity.valueMissing ? t.validationRequired : validity.typeMismatch && field.type === 'email' ? t.validationEmail : validity.tooShort ? t.validationShort : t.validationInvalid)
    }
    const input = event => event.target.setCustomValidity?.('')
    document.querySelectorAll('input,select,textarea').forEach(field=>field.setCustomValidity?.(''))
    document.addEventListener('invalid',invalid,true)
    document.addEventListener('input',input,true)
    return ()=>{document.removeEventListener('invalid',invalid,true);document.removeEventListener('input',input,true)}
  }, [t])

  return (
    <WishlistProvider user={user}><div className="app">
      <a className="skip-link" href="#main-content">{t.skipContent}</a>
      {!['login', 'register'].includes(page) && (
        <Navbar
          user={user}
          onLogout={handleLogout}
          cartItems={cartCount}
          onNavigate={navigate}
          page={page}
          lang={lang}
          toggleLang={toggleLang}
          t={t}
        />
      )}

      <main id="main-content" tabIndex={-1}>
      <WishlistNotice t={t} onNavigate={navigate}/><VerificationNotice user={user} onUser={setUser} t={t} />
      <ScreenBoundary t={t}><Suspense fallback={<div className="loading-m" role="status">{t.loading}</div>}>
      {protectedPages.has(page) && (!authReady || !user) ? <div className="loading-m" role="status">{t.loading}</div> : <>
      {page === 'catalog' && (
        <Catalog t={t} onNavigate={navigate} user={user} onCartChange={handleCartChange} cartQuantities={cartQuantities} searchParams={location.search} onQuery={query} />
      )}

      {page === 'detail' && (
        <ProductDetail
          t={t}
          productId={productId}
          onNavigate={navigate}
          user={user}
          onCartChange={handleCartChange}
        />
      )}

      {page === 'wishlist' && <Wishlist t={t} onNavigate={navigate} onCartChange={handleCartChange} />}
      {page === 'cart' && (
        <Cart t={t} user={user} onNavigate={navigate} onCartChange={handleCartChange} snapshot={cartSnapshot} />
      )}

      {page === 'checkout' && (
        <Checkout t={t} user={user} onNavigate={navigate} onCartChange={handleCartChange} snapshot={cartSnapshot} />
      )}

      {page === 'pedidoConfirmado' && (
        <PedidoConfirmado t={t} user={user} orderId={orderId} onNavigate={navigate} />
      )}

      {page === 'misPedidos' && (
        <MisPedidos t={t} user={user} onNavigate={navigate} searchParams={location.search} onQuery={query} lang={lang} />
      )}

      {page === 'detallePedido' && (
        <DetallePedido t={t} user={user} orderId={orderId} onNavigate={navigate} lang={lang} />
      )}

      {page === 'admin' && (
        <AdminDashboard t={t} user={user} onNavigate={navigate} searchParams={location.search} onQuery={query} />
      )}

      {page === 'profile' && (
        <Profile
          t={t}
          user={user}
          setUser={setUser}
          onNavigate={navigate}
          firebaseUser={firebaseUser}
          firebaseReady={firebaseReady}
        />
      )}

      {page === 'login' && (
        <Login t={t} onNavigate={navigate} onAuth={handleAuth} lang={lang} toggleLang={toggleLang} />
      )}

      {page === 'register' && (
        <Register t={t} onNavigate={navigate} onAuth={handleAuth} lang={lang} toggleLang={toggleLang} />
      )}

      {page === 'verify' && <VerifyEmail t={t} token={routeToken} onNavigate={navigate} onVerified={()=>{if(user)api.get('/auth/me/').then(({data})=>setUser(data)).catch(()=>{})}} />}
      {page === 'forgot' && <ForgotPassword t={t} onNavigate={navigate} />}
      {page === 'reset' && <ResetPassword t={t} token={routeToken} onNavigate={navigate} />}
      {page === 'notFound' && <div className="panel-page"><h1>404</h1><p>{t.pageNotFound}</p><button className="btn-neon" onClick={() => navigate('catalog')}>{t.goToCatalog}</button></div>}
      </>}
      </Suspense></ScreenBoundary>
      </main>
      <ChatLauncher user={user} lang={lang} t={t} onNavigate={navigate} onVisit={visit} onCartChange={handleCartChange} toggleLang={toggleLang} />
    </div></WishlistProvider>
  )
}

export default App
