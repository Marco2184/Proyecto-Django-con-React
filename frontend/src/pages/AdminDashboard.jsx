import { useEffect, useMemo, useState } from 'react'
import { api, getApiError } from '../services/api'

const money = (value) => `S/ ${Number(value || 0).toFixed(2)}`

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
    ;(cat.subcategorias || []).forEach((sub) => rows.push({ id: sub.id, nombre: `— ${sub.nombre}` }))
  })
  return rows
}

export default function AdminDashboard({ user, onNavigate, t }) {
  const [tab, setTab] = useState('resumen')
  const [dashboard, setDashboard] = useState(null)
  const [products, setProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [users, setUsers] = useState([])
  const [options, setOptions] = useState({ categorias: [], plataformas: [] })
  const [productForm, setProductForm] = useState(emptyProduct)
  const [editingProductId, setEditingProductId] = useState(null)
  const [search, setSearch] = useState('')
  const [orderStatus, setOrderStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const categoriasFlat = useMemo(() => flattenCategories(options.categorias), [options.categorias])

  const loadDashboard = async () => {
    const { data } = await api.get('/admin/dashboard/')
    setDashboard(data)
  }

  const loadOptions = async () => {
    const { data } = await api.get('/admin/catalog-options/')
    setOptions(data)
  }

  const loadProducts = async () => {
    const { data } = await api.get('/admin/products/', { params: { q: search } })
    setProducts(data)
  }

  const loadOrders = async () => {
    const { data } = await api.get('/admin/orders/', { params: { q: search, estado: orderStatus } })
    setOrders(data)
  }

  const loadUsers = async () => {
    const { data } = await api.get('/admin/users/', { params: { q: search } })
    setUsers(data)
  }

  const refresh = async (nextTab = tab) => {
    setLoading(true)
    setError('')
    try {
      await loadOptions()
      if (nextTab === 'resumen') await loadDashboard()
      if (nextTab === 'productos') await loadProducts()
      if (nextTab === 'pedidos') await loadOrders()
      if (nextTab === 'usuarios') await loadUsers()
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user?.is_staff) return
    refresh('resumen')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.is_staff])

  useEffect(() => {
    if (!user?.is_staff) return
    refresh(tab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, orderStatus])

  if (!user) {
    return (
      <main className="page-shell admin-page">
        <section className="panel-card admin-access-card">
          <div className="section-tag">ADMIN</div>
          <h1>Acceso requerido</h1>
          <p className="muted">Inicia sesión para entrar al panel administrativo.</p>
          <button className="btn-neon" onClick={() => onNavigate('login')}>{t.login || 'Iniciar sesión'}</button>
        </section>
      </main>
    )
  }

  if (!user.is_staff) {
    return (
      <main className="page-shell admin-page">
        <section className="panel-card admin-access-card">
          <div className="section-tag danger-tag">403</div>
          <h1>Panel administrador</h1>
          <p className="muted">Tu cuenta no tiene permisos de administrador.</p>
          <button className="btn-ghost" onClick={() => onNavigate('catalog')}>Volver al catálogo</button>
        </section>
      </main>
    )
  }

  const switchTab = (nextTab) => {
    setTab(nextTab)
    setSearch('')
    setMessage('')
    setError('')
  }

  const handleSearch = async (event) => {
    event.preventDefault()
    await refresh(tab)
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
        setMessage('Producto actualizado correctamente.')
      } else {
        await api.post('/admin/products/', payload)
        setMessage('Producto creado correctamente.')
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
    if (!window.confirm(`¿Eliminar ${product.nombre}?`)) return
    setSaving(true)
    setError('')
    try {
      await api.delete(`/admin/products/${product.id}/`)
      setMessage('Producto eliminado correctamente.')
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
      setMessage(`Pedido ${order.numero} actualizado.`)
      await loadOrders()
      await loadDashboard().catch(() => {})
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const updateUser = async (targetUser, changes) => {
    if (targetUser.id === user.id && changes.is_staff === false) {
      setError('No puedes quitarte el rol administrador a ti mismo.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.patch('/admin/users/', { id: targetUser.id, ...changes })
      setMessage('Usuario actualizado correctamente.')
      await loadUsers()
    } catch (err) {
      setError(getApiError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="page-shell admin-page">
      <section className="admin-header panel-card">
        <div>
          <div className="section-tag">ADMINISTRADOR</div>
          <h1>Panel Monolith</h1>
          <p className="muted">Gestiona productos, stock, pedidos y usuarios sin alterar el flujo normal de compra.</p>
        </div>
        <div className="admin-current-user">
          <span>Sesión admin</span>
          <strong>{user.email}</strong>
        </div>
      </section>

      <div className="admin-tabs">
        {[
          ['resumen', 'Resumen'],
          ['productos', 'Productos'],
          ['pedidos', 'Pedidos'],
          ['usuarios', 'Usuarios']
        ].map(([key, label]) => (
          <button key={key} className={`admin-tab ${tab === key ? 'active' : ''}`} onClick={() => switchTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {error && <div className="alert-error admin-alert">{error}</div>}
      {message && <div className="alert-success admin-alert">{message}</div>}
      {loading && <div className="panel-card admin-loading">Cargando datos del panel...</div>}

      {!loading && tab === 'resumen' && dashboard && (
        <section className="admin-grid-summary">
          <div className="admin-stat"><span>Ventas totales</span><strong>{money(dashboard.ventas_total)}</strong></div>
          <div className="admin-stat"><span>Ventas hoy</span><strong>{money(dashboard.ventas_hoy)}</strong></div>
          <div className="admin-stat"><span>Pedidos</span><strong>{dashboard.pedidos_total}</strong></div>
          <div className="admin-stat"><span>Usuarios</span><strong>{dashboard.usuarios_total}</strong></div>
          <div className="admin-stat"><span>Productos</span><strong>{dashboard.productos_total}</strong></div>
          <div className="admin-stat danger"><span>Stock bajo</span><strong>{dashboard.stock_bajo_total}</strong></div>

          <section className="panel-card admin-wide-card">
            <h2>Últimos pedidos</h2>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>Número</th><th>Cliente</th><th>Estado</th><th>Total</th></tr></thead>
                <tbody>
                  {(dashboard.ultimos_pedidos || []).map((order) => (
                    <tr key={order.id}><td>{order.numero}</td><td>{order.usuario_email}</td><td>{order.estado}</td><td>{money(order.monto_total)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel-card admin-wide-card">
            <h2>Productos con stock bajo</h2>
            <div className="admin-stock-list">
              {(dashboard.stock_bajo || []).map((product) => (
                <div className="admin-stock-item" key={product.id}>
                  <span>{product.nombre}</span>
                  <strong>{product.stock} unidades</strong>
                </div>
              ))}
            </div>
          </section>
        </section>
      )}

      {!loading && tab === 'productos' && (
        <section className="admin-section-grid">
          <form className="panel-card admin-product-form" onSubmit={saveProduct}>
            <h2>{editingProductId ? 'Editar producto' : 'Nuevo producto'}</h2>
            <label>Nombre<input value={productForm.nombre} onChange={(e) => setProductForm({ ...productForm, nombre: e.target.value })} required /></label>
            <label>Descripción<textarea value={productForm.descripcion} onChange={(e) => setProductForm({ ...productForm, descripcion: e.target.value })} rows="4" /></label>
            <div className="admin-form-row">
              <label>Precio<input type="number" step="0.01" value={productForm.precio} onChange={(e) => setProductForm({ ...productForm, precio: e.target.value })} required /></label>
              <label>Precio original<input type="number" step="0.01" value={productForm.precio_original || ''} onChange={(e) => setProductForm({ ...productForm, precio_original: e.target.value })} /></label>
              <label>Stock<input type="number" value={productForm.stock} onChange={(e) => setProductForm({ ...productForm, stock: e.target.value })} required /></label>
            </div>
            <label>Imagen URL<input value={productForm.imagen_url} onChange={(e) => setProductForm({ ...productForm, imagen_url: e.target.value })} /></label>
            <label>Categoría
              <select value={productForm.categoria_id || ''} onChange={(e) => setProductForm({ ...productForm, categoria_id: e.target.value })}>
                <option value="">Sin categoría</option>
                {categoriasFlat.map((cat) => <option key={cat.id} value={cat.id}>{cat.nombre}</option>)}
              </select>
            </label>
            <div className="admin-platforms">
              <span>Plataformas</span>
              <div>
                {(options.plataformas || []).map((platform) => (
                  <button type="button" key={platform.id} className={productForm.plataforma_ids.includes(platform.id) ? 'selected' : ''} onClick={() => togglePlatform(platform.id)}>
                    {platform.nombre}
                  </button>
                ))}
              </div>
            </div>
            <div className="row-actions">
              <button className="btn-neon" disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</button>
              {editingProductId && <button type="button" className="btn-ghost" onClick={resetProductForm}>Cancelar edición</button>}
            </div>
          </form>

          <section className="panel-card admin-list-card">
            <div className="admin-list-head">
              <h2>Inventario</h2>
              <form onSubmit={handleSearch} className="admin-search"><input placeholder="Buscar producto..." value={search} onChange={(e) => setSearch(e.target.value)} /><button>Buscar</button></form>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>Producto</th><th>Precio</th><th>Stock</th><th>Plataformas</th><th>Acciones</th></tr></thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td>{product.nombre}</td>
                      <td>{money(product.precio)}</td>
                      <td className={product.stock <= 5 ? 'danger-cell' : ''}>{product.stock}</td>
                      <td>{(product.plataformas || []).map((p) => p.nombre).join(', ') || '—'}</td>
                      <td className="admin-actions"><button onClick={() => editProduct(product)}>Editar</button><button onClick={() => deleteProduct(product)}>Eliminar</button></td>
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
            <h2>Gestión de pedidos</h2>
            <form onSubmit={handleSearch} className="admin-search">
              <input placeholder="Buscar por número, cliente o correo..." value={search} onChange={(e) => setSearch(e.target.value)} />
              <select value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                <option value="">Todos los estados</option>
                <option value="pendiente">Pendiente</option>
                <option value="procesando">Procesando</option>
                <option value="enviado">Enviado</option>
                <option value="entregado">Entregado</option>
                <option value="cancelado">Cancelado</option>
              </select>
              <button>Filtrar</button>
            </form>
          </div>
          <div className="admin-orders-list">
            {orders.map((order) => (
              <article className="admin-order-card" key={order.id}>
                <div><strong>{order.numero}</strong><span>{order.usuario_nombre} · {order.usuario_email}</span></div>
                <div><span>Total</span><strong>{money(order.monto_total)}</strong></div>
                <div><span>Estado</span><strong>{order.estado}</strong></div>
                <select value={order.estado} onChange={(e) => updateOrderStatus(order, e.target.value)} disabled={saving}>
                  <option value="pendiente">Pendiente</option>
                  <option value="procesando">Procesando</option>
                  <option value="enviado">Enviado</option>
                  <option value="entregado">Entregado</option>
                  <option value="cancelado">Cancelado</option>
                </select>
              </article>
            ))}
          </div>
        </section>
      )}

      {!loading && tab === 'usuarios' && (
        <section className="panel-card admin-list-card">
          <div className="admin-list-head">
            <h2>Usuarios</h2>
            <form onSubmit={handleSearch} className="admin-search"><input placeholder="Buscar usuario..." value={search} onChange={(e) => setSearch(e.target.value)} /><button>Buscar</button></form>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead><tr><th>Nombre</th><th>Email</th><th>Pedidos</th><th>Activo</th><th>Admin</th></tr></thead>
              <tbody>
                {users.map((row) => (
                  <tr key={row.id}>
                    <td>{row.nombre}</td>
                    <td>{row.email}</td>
                    <td>{row.pedidos_count || 0}</td>
                    <td><button className={row.cuenta_activa ? 'admin-toggle on' : 'admin-toggle'} onClick={() => updateUser(row, { cuenta_activa: !row.cuenta_activa, is_active: !row.cuenta_activa })}>{row.cuenta_activa ? 'Activo' : 'Inactivo'}</button></td>
                    <td><button className={row.is_staff ? 'admin-toggle on' : 'admin-toggle'} onClick={() => updateUser(row, { is_staff: !row.is_staff })}>{row.is_staff ? 'Admin' : 'Usuario'}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  )
}
