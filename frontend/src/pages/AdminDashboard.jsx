import AdminPromotions from '../components/AdminPromotions'
import AdminAnalytics from '../components/AdminAnalytics'
import AdminInventory from '../components/AdminInventory'
import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'
import { getTranslatedCategory, getTranslatedOrderStatus, getTranslatedText } from '../i18n'
import useDraft from '../hooks/useDraft'

const money = (value) => `S/ ${Number(value || 0).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}`

const emptyProduct = {
  nombre: '',
  descripcion: '',
  precio: '',
  precio_original: '',
  stock: 0,
  imagen_url: '',
  categoria_id: '',
  plataforma_ids: [],
  valoracion: 0,
  ventas: 0,
  especificaciones: {}
}

function flattenCategories(categorias = []) {
  const rows = []
  categorias.forEach((cat) => {
    rows.push({ id: cat.id, nombre: cat.nombre })
    ;(cat.subcategorias || []).forEach((sub) => rows.push({ id: sub.id, nombre: sub.nombre }))
  })
  return rows
}

function isDeletedUser(row) {
  const email = String(row?.email || '').trim().toLowerCase()
  const nombre = String(row?.nombre || '').trim().toLowerCase()

  return (
    email.endsWith('@monolith.void') ||
    email.startsWith('deleted_') ||
    nombre === 'usuario eliminado' ||
    nombre === 'deleted user' ||
    nombre === 'usuario_eliminado'
  )
}

export default function AdminDashboard({ user, onNavigate, t, searchParams, onQuery }) {
  const params = new URLSearchParams(searchParams)
  const tab = ['productos','pedidos','usuarios','inventario','promociones'].includes(params.get('tab')) ? params.get('tab') : 'resumen'
  const setTab = value => onQuery({tab:value === 'resumen' ? null : value, search:null, estado:null, page:null})
  const page=Number(params.get('page')||1)
  const [pagination,setPagination]=useState({})
  const activeSearch = params.get('search') || ''
  const [dashboard, setDashboard] = useState(null)
  const [products, setProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [users, setUsers] = useState([])
  const [options, setOptions] = useState({ categorias: [], plataformas: [] })
  const [productForm, setProductForm] = useDraft(`monolith-draft:admin-product:${user.id}`, emptyProduct)
  const [editingProductId, setEditingProductId] = useDraft(`monolith-draft:admin-product-id:${user.id}`, null)
  const [search, setSearch] = useState(activeSearch)
  useEffect(() => setSearch(activeSearch), [activeSearch])
  const orderStatus = params.get('estado') || ''
  const setOrderStatus = value => onQuery({estado:value,page:null})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const categoriasFlat = useMemo(() => flattenCategories(options.categorias), [options.categorias])

  const loadDashboard = async (signal) => {
    const { data } = await api.get('/admin/dashboard/', {params:{desde:params.get('desde')||undefined,hasta:params.get('hasta')||undefined},signal})
    if (!signal?.aborted) setDashboard(data)
  }

  const loadOptions = async (signal) => {
    const { data } = await api.get('/admin/catalog-options/', {signal})
    if (!signal?.aborted) setOptions(data)
  }

  const loadProducts = async (signal) => {
    const { data } = await api.get('/admin/products/', { params: { q: activeSearch,page }, signal })
    if (!signal?.aborted) {setProducts(data.results||data);setPagination({next:data.next,previous:data.previous,count:data.count})}
  }

  const loadOrders = async (signal) => {
    const { data } = await api.get('/admin/orders/', { params: { q: activeSearch, estado: orderStatus,page }, signal })
    if (!signal?.aborted) {setOrders(data.results||data);setPagination({next:data.next,previous:data.previous,count:data.count})}
  }

  const loadUsers = async (signal) => {
    const { data } = await api.get('/admin/users/', { params: { q: activeSearch,page }, signal })
    if (!signal?.aborted) {setUsers(data.results||data);setPagination({next:data.next,previous:data.previous,count:data.count})}
  }

  const refresh = async (nextTab = tab, signal) => {
    setLoading(true)
    setError('')
    try {
      if (nextTab === 'resumen') await loadDashboard(signal)
      if (nextTab === 'productos') await Promise.all([loadOptions(signal),loadProducts(signal)])
      if (nextTab === 'pedidos') await loadOrders(signal)
      if (nextTab === 'usuarios') await loadUsers(signal)
    } catch (err) {
      if (!signal?.aborted) setError(getApiError(err))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  useEffect(() => {
    if (!user?.is_staff) return
    const controller = new AbortController()
    refresh(tab, controller.signal)
    return () => controller.abort()
  }, [user?.is_staff, tab, orderStatus, activeSearch, page, params.get('desde'), params.get('hasta')])

  if (!user) {
    return (
      <section className="page-shell admin-page">
        <section className="panel-card admin-access-card">
          <div className="section-tag">ADMIN</div>
          <h1>{t.accessRequired}</h1>
          <p className="muted">{t.adminSignIn}</p>
          <button className="btn-neon" onClick={() => onNavigate('login')}>{t.login}</button>
        </section>
      </section>
    )
  }

  if (!user.is_staff) {
    return (
      <section className="page-shell admin-page">
        <section className="panel-card admin-access-card">
          <div className="section-tag danger-tag">403</div>
          <h1>{t.adminPanel}</h1>
          <p className="muted">{t.adminAccessDenied}</p>
          <button className="btn-ghost" onClick={() => onNavigate('catalog')}>{t.backToCatalog}</button>
        </section>
      </section>
    )
  }

  const switchTab = (nextTab) => {
    setTab(nextTab)
    setSearch('')
    setMessage('')
    setError('')
  }

  const handleSearch = (event) => {
    event.preventDefault()
    onQuery({search,page:null})
  }

  const resetProductForm = () => {
    setProductForm(emptyProduct)
    setEditingProductId(null)
  }

  const editProduct = (product) => {
    setEditingProductId(product.id)
    setProductForm({
      nombre: product.nombre || '',
      descripcion: product.descripcion || '',
      precio: product.precio || '',
      precio_original: product.precio_original || '',
      stock: product.stock || 0,
      imagen_url: product.imagen_url || '',
      categoria_id: product.categoria?.id || '',
      plataforma_ids: (product.plataformas || []).map((platform) => platform.id),
      valoracion: product.valoracion || 0,
      ventas: product.ventas || 0,
      especificaciones: product.especificaciones || {}
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const togglePlatform = (platformId) => {
    setProductForm((current) => {
      const exists = current.plataforma_ids.includes(platformId)
      return {
        ...current,
        plataforma_ids: exists
          ? current.plataforma_ids.filter((id) => id !== platformId)
          : [...current.plataforma_ids, platformId]
      }
    })
  }

  const saveProduct = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')

    const payload = {
      ...productForm,
      categoria_id: productForm.categoria_id || null,
      precio_original: productForm.precio_original || null,
      precio: Number(productForm.precio || 0),
      stock: Number(productForm.stock || 0),
      valoracion: Number(productForm.valoracion || 0),
      ventas: Number(productForm.ventas || 0)
    }

    try {
      if (editingProductId) {
        await api.patch(`/admin/products/${editingProductId}/`, payload)
        setMessage(t.adminProductUpdated)
      } else {
        await api.post('/admin/products/', payload)
        setMessage(t.adminProductCreated)
      }
      resetProductForm()
      await loadProducts()
      await loadDashboard().catch(() => {})
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const deleteProduct = async (product) => {
    if (!window.confirm(`${t.adminConfirmDeleteProduct} ${getTranslatedText(t, product.nombre)}`)) return
    setSaving(true)
    setError('')
    try {
      await api.delete(`/admin/products/${product.id}/`)
      setMessage(t.adminProductDeleted)
      await loadProducts()
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const updateOrderStatus = async (order, estado) => {
    setSaving(true)
    setError('')
    try {
      await api.patch(`/admin/orders/${order.id}/`, { estado })
      setMessage(`${t.adminOrderUpdated} ${order.numero}`)
      await loadOrders()
      await loadDashboard().catch(() => {})
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const updateUser = async (targetUser, changes) => {
    if (isDeletedUser(targetUser)) {
      setError(t.cannotChangeDeleted)
      return
    }

    if (targetUser.id === user.id && (changes.is_staff === false || changes.is_superuser === false)) {
      setError(t.cannotRemoveOwnAdmin)
      return
    }

    if (targetUser.id === user.id && (changes.is_active === false || changes.cuenta_activa === false)) {
      setError(t.cannotDeactivateOwnAdmin)
      return
    }

    setSaving(true)
    setError('')
    try {
      await api.patch('/admin/users/', { id: targetUser.id, ...changes })
      setMessage(t.adminUserUpdated)
      await loadUsers()
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="page-shell admin-page">
      <section className="admin-header panel-card">
        <div>
          <div className="section-tag">{t.admin}</div>
          <h1>{t.adminMonolith}</h1>
          <p className="muted">{t.adminIntro}</p>
        </div>
        <div className="admin-current-user">
          <span>{t.adminSession}</span>
          <strong>{user.email}</strong>
        </div>
      </section>

      <div className="admin-tabs">
        {[
          ['resumen', t.adminSummary],
          ['productos', t.adminProducts],
          ['pedidos', t.adminOrders],
          ['usuarios', t.adminUsers], ['inventario', t.stockHistory], ['promociones', t.promotions]
        ].map(([key, label]) => (
          <button key={key} aria-pressed={tab===key} className={`admin-tab ${tab === key ? 'active' : ''}`} onClick={() => switchTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {error && <div className="alert-error admin-alert" role="alert">{getTranslatedText(t, error)}</div>}
      {message && <div className="alert-success admin-alert" role="status">{getTranslatedText(t, message)}</div>}
      {loading && <div className="panel-card admin-loading" role="status">{t.adminLoading}</div>}

      {!loading && tab === 'promociones' && <AdminPromotions t={t}/>}
      {!loading && tab === 'inventario' && <AdminInventory t={t}/>}
      {!loading && tab === 'resumen' && dashboard && (
        <section className="admin-grid-summary"><AdminAnalytics data={dashboard} t={t} desde={params.get('desde')} hasta={params.get('hasta')} onDates={(desde,hasta)=>onQuery({desde,hasta})}/>
          <div className="admin-stat"><span>{t.adminTotalSales}</span><strong>{money(dashboard.ventas_total)}</strong></div>
          <div className="admin-stat"><span>{t.adminTodaySales}</span><strong>{money(dashboard.ventas_hoy)}</strong></div>
          <div className="admin-stat"><span>{t.adminOrders}</span><strong>{dashboard.pedidos_total}</strong></div>
          <div className="admin-stat"><span>{t.adminUsers}</span><strong>{dashboard.usuarios_total}</strong></div>
          <div className="admin-stat"><span>{t.adminProducts}</span><strong>{dashboard.productos_total}</strong></div>
          <div className="admin-stat danger"><span>{t.adminLowStock}</span><strong>{dashboard.stock_bajo_total}</strong></div>

          <section className="panel-card admin-wide-card">
            <h2>{t.adminLatestOrders}</h2>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>{t.orderNumber}</th><th>{t.customer}</th><th>{t.adminStatus}</th><th>{t.total}</th></tr></thead>
                <tbody>
                  {(dashboard.ultimos_pedidos || []).map((order) => (
                    <tr key={order.id}><td>{order.numero}</td><td>{order.usuario_email}</td><td>{getTranslatedOrderStatus(t, order.estado)}</td><td>{money(order.monto_total)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel-card admin-wide-card">
            <h2>{t.adminLowStockProducts}</h2>
            <div className="admin-stock-list">
              {(dashboard.stock_bajo || []).map((product) => (
                <div className="admin-stock-item" key={product.id}>
                  <span>{getTranslatedText(t, product.nombre)}</span>
                  <strong>{product.stock} {t.units}</strong>
                </div>
              ))}
            </div>
          </section>
        </section>
      )}

      {!loading && tab === 'productos' && (
        <section className="admin-section-grid">
          <form className="panel-card admin-product-form" onSubmit={saveProduct}>
            <h2>{editingProductId ? t.adminEditProduct : t.adminCreateProduct}</h2>
            <label>{t.productName}<input value={productForm.nombre} onChange={(e) => setProductForm({ ...productForm, nombre: e.target.value })} required /></label>
            <label>{t.description}<textarea value={productForm.descripcion} onChange={(e) => setProductForm({ ...productForm, descripcion: e.target.value })} rows="4" /></label>
            <div className="admin-form-row">
              <label>{t.price}<input type="number" step="0.01" value={productForm.precio} onChange={(e) => setProductForm({ ...productForm, precio: e.target.value })} required /></label>
              <label>{t.originalPrice}<input type="number" step="0.01" value={productForm.precio_original || ''} onChange={(e) => setProductForm({ ...productForm, precio_original: e.target.value })} /></label>
              <label>{t.reason}<input maxLength="250" value={productForm.motivo_stock||''} onChange={e=>setProductForm({...productForm,motivo_stock:e.target.value})}/></label>
              <label>{t.stock}<input type="number" value={productForm.stock} onChange={(e) => setProductForm({ ...productForm, stock: e.target.value })} required /></label>
            </div>
            <label>{t.imageUrl}<input value={productForm.imagen_url} onChange={(e) => setProductForm({ ...productForm, imagen_url: e.target.value })} /></label>
            <label>{t.category}
              <select value={productForm.categoria_id || ''} onChange={(e) => setProductForm({ ...productForm, categoria_id: e.target.value })}>
                <option value="">{t.noCategory}</option>
                {categoriasFlat.map((cat) => <option key={cat.id} value={cat.id}>{getTranslatedCategory(t, cat)}</option>)}
              </select>
            </label>
            <div className="admin-platforms">
              <span>{t.platforms}</span>
              <div>
                {(options.plataformas || []).map((platform) => (
                  <button type="button" key={platform.id} className={productForm.plataforma_ids.includes(platform.id) ? 'selected' : ''} onClick={() => togglePlatform(platform.id)}>
                    {platform.nombre}
                  </button>
                ))}
              </div>
            </div>
            <div className="row-actions">
              <button className="btn-neon" disabled={saving}>{saving ? t.saving : t.save}</button>
              {editingProductId && <button type="button" className="btn-ghost" onClick={resetProductForm}>{t.cancelEdit}</button>}
            </div>
          </form>

          <section className="panel-card admin-list-card">
            <div className="admin-list-head">
              <h2>{t.inventory}</h2>
              <form onSubmit={handleSearch} className="admin-search"><input placeholder={t.searchProduct} value={search} onChange={(e) => setSearch(e.target.value)} /><button>{t.search}</button></form>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>{t.productImage}</th><th>{t.price}</th><th>{t.stock}</th><th>{t.platforms}</th><th>{t.actions}</th></tr></thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td><small>#{product.id}</small> {getTranslatedText(t, product.nombre)}</td>
                      <td>{money(product.precio)}</td>
                      <td className={product.stock <= 5 ? 'danger-cell' : ''}>{product.stock}</td>
                      <td>{(product.plataformas || []).map((p) => p.nombre).join(', ') || '—'}</td>
                      <td className="admin-actions"><button onClick={() => editProduct(product)}>{t.edit}</button><button onClick={() => deleteProduct(product)}>{t.delete}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      )}

      {!loading && tab === 'pedidos' && (
        <section className="panel-card admin-list-card">
          <div className="admin-list-head">
            <h2>{t.manageOrders}</h2>
            <form onSubmit={handleSearch} className="admin-search">
              <input placeholder={t.searchAdminOrders} value={search} onChange={(e) => setSearch(e.target.value)} />
              <select value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                <option value="">{t.allStatuses}</option>
                <option value="pendiente">{t.orderPending}</option>
                <option value="procesando">{t.orderProcessing}</option>
                <option value="enviado">{t.orderShipped}</option>
                <option value="entregado">{t.orderDelivered}</option>
                <option value="cancelado">{t.orderCancelled}</option>
              </select>
              <button>{t.filter}</button>
            </form>
          </div>
          <div className="admin-orders-list">
            {orders.map((order) => (
              <article className="admin-order-card" key={order.id}>
                <div><strong>{order.numero}</strong><span>{order.usuario_nombre} · {order.usuario_email}</span></div>
                <div><span>{t.total}</span><strong>{money(order.monto_total)}</strong></div>
                <div><span>{t.adminStatus}</span><strong>{getTranslatedOrderStatus(t, order.estado)}</strong></div>
                <select value={order.estado} onChange={(e) => updateOrderStatus(order, e.target.value)} disabled={saving}>
                  {[order.estado, ...({ pendiente:['procesando','cancelado'], procesando:['enviado','cancelado'], enviado:['entregado'], entregado:[], cancelado:[] }[order.estado] || [])].map(state => (
                    <option key={state} value={state}>{getTranslatedOrderStatus(t, state)}</option>
                  ))}
                </select>
              </article>
            ))}
          </div>
        </section>
      )}

      {!loading && tab === 'usuarios' && (
        <section className="panel-card admin-list-card">
          <div className="admin-list-head">
            <h2>{t.adminUsers}</h2>
            <form onSubmit={handleSearch} className="admin-search"><input placeholder={t.searchUser} value={search} onChange={(e) => setSearch(e.target.value)} /><button>{t.search}</button></form>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead><tr><th>{t.productName}</th><th>{t.email}</th><th>{t.adminOrders}</th><th>{t.adminActive}</th><th>{t.adminRole}</th></tr></thead>
              <tbody>
                {users.map((row) => {
                  const deleted = isDeletedUser(row)
                  const isSelf = row.id === user.id
                  const isAdmin = Boolean(row.is_staff || row.is_superuser)
                  const canToggleActive = !deleted && !isSelf && (!row.is_superuser || user.is_superuser)
                  const canToggleAdmin = !deleted && !isSelf && user.is_superuser

                  return (
                    <tr key={row.id} className={deleted ? 'admin-row-disabled' : ''}>
                      <td>{row.nombre}</td>
                      <td>{row.email}</td>
                      <td>{row.pedidos_count || 0}</td>
                      <td>
                        <button
                          className={row.cuenta_activa ? 'admin-toggle on' : 'admin-toggle'}
                          disabled={!canToggleActive || saving}
                          onClick={() => updateUser(row, { cuenta_activa: !row.cuenta_activa, is_active: !row.cuenta_activa })}
                          title={deleted ? t.deletedAccountLocked : isSelf ? t.cannotDeactivateSelf : ''}
                        >
                          {deleted ? t.deleted : row.cuenta_activa ? t.adminActive : t.adminInactive}
                        </button>
                      </td>
                      <td>
                        <button
                          className={isAdmin ? 'admin-toggle on' : 'admin-toggle'}
                          disabled={!canToggleAdmin || saving}
                          onClick={() => updateUser(row, { is_staff: !isAdmin, is_superuser: !isAdmin })}
                          title={deleted ? t.deletedAccountLocked : isSelf ? t.cannotRemoveOwnRole : ''}
                        >
                          {deleted ? t.locked : isAdmin ? 'Admin' : t.adminNormalUser}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {!loading && ['productos','pedidos','usuarios'].includes(tab) && <div className="row-actions"><button className="btn-ghost" disabled={!pagination.previous} onClick={()=>onQuery({page:page-1})}>{t.previousPage}</button><span>{t.page} {page}</span><button className="btn-ghost" disabled={!pagination.next} onClick={()=>onQuery({page:page+1})}>{t.nextPage}</button></div>}
    </section>
  )
}
