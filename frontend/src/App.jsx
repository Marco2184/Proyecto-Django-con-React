import { useEffect, useMemo, useState } from 'react'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import './styles/global.css'
import './styles/app.css'
import Navbar from './components/Navbar'
import Catalog from './pages/Catalog'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'
import Cart from './pages/Cart'
import ProductDetail from './pages/ProductDetail'
import VerifyEmail from './pages/VerifyEmail'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import Checkout from './pages/Checkout'
import MisPedidos from './pages/MisPedidos'
import DetallePedido from './pages/DetallePedido'
import PedidoConfirmado from './pages/PedidoConfirmado'
import { api, bootstrapAuth, setAuthToken } from './services/api'
import { auth } from './services/firebase'
import { dict } from './i18n'

function readRoute() {
  const path = window.location.pathname
  if (path.startsWith('/verify/')) return { page: 'verify', token: path.split('/')[2] }
  if (path.startsWith('/reset-password/')) return { page: 'reset', token: path.split('/')[2] }
  if (path.startsWith('/producto/')) return { page: 'detail', productId: path.split('/')[2] }
  return { page: 'catalog' }
}

function App() {
  const route = readRoute()
  const [page, setPage] = useState(route.page)
  const [routeToken] = useState(route.token)
  const [productId, setProductId] = useState(route.productId)
  const [orderId, setOrderId] = useState(null)
  const [lastPedido, setLastPedido] = useState(null)
  const [user, setUser] = useState(null)
  const [firebaseUser, setFirebaseUser] = useState(null)
  const [firebaseReady, setFirebaseReady] = useState(false)
  const [cartCount, setCartCount] = useState(0)
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'es')
  const t = useMemo(() => dict[lang], [lang])

  useEffect(() => {
    let mounted = true

    const initBackendSession = async () => {
      const nextUser = await bootstrapAuth()

      if (!mounted) return

      if (nextUser) {
        setUser(nextUser)
        fetchCartCount()
      } else {
        setUser(null)
        setCartCount(0)
      }
    }

    initBackendSession()

    const unsubscribe = onAuthStateChanged(auth, (nextFirebaseUser) => {
      if (!mounted) return
      setFirebaseUser(nextFirebaseUser)
      setFirebaseReady(true)
    })

    return () => {
      mounted = false
      unsubscribe()
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('lang', lang)
    api.post('/i18n/set-language/', { language: lang }).catch(() => {})
  }, [lang])

  const fetchUser = async () => {
    try {
      const { data } = await api.get('/auth/me/')
      setUser(data)
      fetchCartCount()
    } catch {
      setAuthToken(null)
      setUser(null)
      setCartCount(0)
    }
  }

  const fetchCartCount = async () => {
    try {
      const { data } = await api.get('/cart/')
      setCartCount(data.cantidad_items || 0)
    } catch {
      setCartCount(0)
    }
  }

  const navigate = (nextPage, payload = {}) => {
    setPage(nextPage)

    if (payload.productId) {
      setProductId(payload.productId)
    }

    if (payload.orderId) {
      setOrderId(payload.orderId)
    }

    if (payload.pedido) {
      setLastPedido(payload.pedido)
    }

    if (nextPage === 'detail' && payload.productId) {
      window.history.pushState({}, '', `/producto/${payload.productId}`)
    } else if (!['verify', 'reset'].includes(nextPage)) {
      window.history.pushState({}, '', '/')
    }
  }

  const handleAuth = (token, nextUser) => {
    setAuthToken(token)
    setUser(nextUser)
    fetchCartCount()
    navigate('catalog')
  }

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout/')
    } catch {}

    try {
      await signOut(auth)
    } catch {}

    setAuthToken(null)
    setUser(null)
    setFirebaseUser(null)
    setCartCount(0)
    navigate('catalog')
  }

  const toggleLang = () => setLang(lang === 'es' ? 'en' : 'es')

  return (
    <div className="app">
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

      {page === 'catalog' && (
        <Catalog t={t} onNavigate={navigate} user={user} onCartChange={fetchCartCount} />
      )}

      {page === 'detail' && (
        <ProductDetail
          t={t}
          productId={productId}
          onNavigate={navigate}
          user={user}
          onCartChange={fetchCartCount}
        />
      )}

      {page === 'cart' && (
        <Cart t={t} user={user} onNavigate={navigate} onCartChange={fetchCartCount} />
      )}

      {page === 'checkout' && (
        <Checkout t={t} user={user} onNavigate={navigate} onCartChange={fetchCartCount} />
      )}

      {page === 'pedidoConfirmado' && (
        <PedidoConfirmado t={t} orderId={orderId} pedido={lastPedido} onNavigate={navigate} />
      )}

      {page === 'misPedidos' && (
        <MisPedidos t={t} user={user} onNavigate={navigate} />
      )}

      {page === 'detallePedido' && (
        <DetallePedido t={t} user={user} orderId={orderId} onNavigate={navigate} />
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

      {page === 'verify' && <VerifyEmail t={t} token={routeToken} onNavigate={navigate} />}
      {page === 'forgot' && <ForgotPassword t={t} onNavigate={navigate} />}
      {page === 'reset' && <ResetPassword t={t} token={routeToken} onNavigate={navigate} />}
    </div>
  )
}

export default App
