import { useEffect, useState } from 'react'
import { api, getApiError, setAuthToken } from '../services/api'
import { getTranslatedOrderStatus, getTranslatedText } from '../i18n'

const depas = [
  'Amazonas',
  'Áncash',
  'Apurímac',
  'Arequipa',
  'Ayacucho',
  'Cajamarca',
  'Callao',
  'Cusco',
  'Huancavelica',
  'Huánuco',
  'Ica',
  'Junín',
  'La Libertad',
  'Lambayeque',
  'Lima',
  'Loreto',
  'Madre de Dios',
  'Moquegua',
  'Pasco',
  'Piura',
  'Puno',
  'San Martín',
  'Tacna',
  'Tumbes',
  'Ucayali'
]

export default function Profile({ t, user, setUser, onNavigate }) {
  const [profile, setProfile] = useState(user || {})
  const [pass, setPass] = useState({
    password_actual: '',
    password_nueva: ''
  })
  const [addresses, setAddresses] = useState([])
  const [addr, setAddr] = useState({
    calle: '',
    ciudad: '',
    departamento: 'Arequipa',
    codigo_postal: '',
    predeterminada: false
  })
  const [editingAddressId, setEditingAddressId] = useState(null)
  const [orders, setOrders] = useState([])
  const [filters, setFilters] = useState({
    estado: '',
    fecha_desde: '',
    fecha_hasta: ''
  })
  const [deletePassword, setDeletePassword] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!user) {
      onNavigate('login')
      return
    }

    loadAddresses()
    loadOrders()
  }, [user])

  const safe = async (fn) => {
    setMsg('')
    setError('')

    try {
      await fn()
    } catch (err) {
      setError(getApiError(err))
    }
  }

  const loadAddresses = () =>
    api.get('/profile/addresses/').then(({ data }) => setAddresses(data))

  const loadOrders = () => {
    const params = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value)
    )

    return api.get(`/profile/orders/?${params}`).then(({ data }) => {
      setOrders(data)
    })
  }

  const saveProfile = (event) =>
    safe(async () => {
      event.preventDefault()

      const { data } = await api.patch('/auth/me/', {
        nombre: profile.nombre,
        telefono: profile.telefono
      })

      setProfile(data)
      setUser(data)
      setMsg(t.profileUpdated)
    })

  const resend = () =>
    safe(async () => {
      const { data } = await api.post('/auth/resend-verification/')
      setMsg(getTranslatedText(t, data.message))
    })

  const changePassword = (event) =>
    safe(async () => {
      event.preventDefault()

      const { data } = await api.post('/auth/change-password/', pass)

      setAuthToken(data.token)
      setPass({
        password_actual: '',
        password_nueva: ''
      })
      setMsg(getTranslatedText(t, data.message))
    })

  const addAddress = (event) =>
    safe(async () => {
      event.preventDefault()

      if (editingAddressId) {
        await api.patch(`/profile/addresses/${editingAddressId}/`, addr)
        setMsg(t.addressUpdated)
      } else {
        await api.post('/profile/addresses/', addr)
        setMsg(t.addressAdded)
      }

      setEditingAddressId(null)
      setAddr({
        calle: '',
        ciudad: '',
        departamento: 'Arequipa',
        codigo_postal: '',
        predeterminada: false
      })

      await loadAddresses()
    })

  const editAddress = (address) => {
    setEditingAddressId(address.id)
    setAddr({
      calle: address.calle,
      ciudad: address.ciudad,
      departamento: address.departamento,
      codigo_postal: address.codigo_postal || '',
      predeterminada: !!address.predeterminada
    })
  }

  const cancelEditAddress = () => {
    setEditingAddressId(null)
    setAddr({
      calle: '',
      ciudad: '',
      departamento: 'Arequipa',
      codigo_postal: '',
      predeterminada: false
    })
  }

  const delAddress = (id) =>
    safe(async () => {
      await api.delete(`/profile/addresses/${id}/`)
      await loadAddresses()
      setMsg(t.addressDeleted)
    })

  const applyFilters = (event) =>
    safe(async () => {
      event.preventDefault()
      await loadOrders()
    })

  const deleteAccount = (event) =>
    safe(async () => {
      event.preventDefault()

      if (!window.confirm(t.deleteAccountConfirm)) {
        return
      }

      await api.post('/auth/delete-account/', {
        password: deletePassword
      })

      setAuthToken(null)
      setUser(null)
      onNavigate('catalog')
    })

  if (!user) {
    return null
  }

  return (
    <div className="panel-page">
      <div className="section-tag">{t.accountTag}</div>
      <h1>{t.profileTitle}</h1>

      {msg && <div className="alert success">{msg}</div>}
      {error && <div className="alert error">{error}</div>}

      {!profile.email_verificado && (
        <div className="alert warn">
          {t.emailNotVerified}{' '}
          <button className="link-neon" onClick={resend}>
            {t.resend}
          </button>
        </div>
      )}

      <section className="panel-card activity-card">
        <h2>{t.recentActivity}</h2>

        <div className="activity-grid">
          <div>
            <strong>
              {profile.email_verificado ? t.verifiedEmail : t.pendingEmail}
            </strong>
            <span>{t.emailAuthStatus}</span>
          </div>

          <div>
            <strong>{addresses.length}</strong>
            <span>{t.savedAddresses}</span>
          </div>

          <div>
            <strong>{orders.length}</strong>
            <span>{t.visibleOrders}</span>
          </div>

          <div>
            <strong>
              {orders[0]?.estado
                ? getTranslatedOrderStatus(t, orders[0].estado)
                : t.noOrders}
            </strong>
            <span>{t.lastRegisteredStatus}</span>
          </div>
        </div>
      </section>

      <div className="profile-grid">
        <section className="panel-card">
          <h2>{t.profileData}</h2>

          <form className="form-stack" onSubmit={saveProfile}>
            <label>{t.name}</label>
            <input
              className="input-m"
              value={profile.nombre || ''}
              onChange={(event) =>
                setProfile({
                  ...profile,
                  nombre: event.target.value
                })
              }
            />

            <label>{t.email}</label>
            <input className="input-m" value={profile.email || ''} disabled />

            <label>{t.phone}</label>
            <input
              className="input-m"
              value={profile.telefono || ''}
              onChange={(event) =>
                setProfile({
                  ...profile,
                  telefono: event.target.value
                })
              }
            />

            <button className="btn-neon">{t.save}</button>
          </form>
        </section>

        <section className="panel-card">
          <h2>{t.changePassword}</h2>

          <form className="form-stack" onSubmit={changePassword}>
            <label>{t.currentPassword}</label>
            <input
              className="input-m"
              type="password"
              value={pass.password_actual}
              onChange={(event) =>
                setPass({
                  ...pass,
                  password_actual: event.target.value
                })
              }
            />

            <label>{t.newPassword}</label>
            <input
              className="input-m"
              type="password"
              value={pass.password_nueva}
              onChange={(event) =>
                setPass({
                  ...pass,
                  password_nueva: event.target.value
                })
              }
            />

            <button className="btn-outline-neon">{t.updatePassword}</button>
          </form>
        </section>
      </div>

      <section className="panel-card">
        <h2>{t.addresses}</h2>

        <form className="address-form" onSubmit={addAddress}>
          <input
            className="input-m"
            placeholder={t.street}
            value={addr.calle}
            onChange={(event) =>
              setAddr({
                ...addr,
                calle: event.target.value
              })
            }
            required
          />

          <input
            className="input-m"
            placeholder={t.city}
            value={addr.ciudad}
            onChange={(event) =>
              setAddr({
                ...addr,
                ciudad: event.target.value
              })
            }
            required
          />

          <select
            className="input-m"
            value={addr.departamento}
            onChange={(event) =>
              setAddr({
                ...addr,
                departamento: event.target.value
              })
            }
          >
            {depas.map((depa) => (
              <option key={depa}>{depa}</option>
            ))}
          </select>

          <input
            className="input-m"
            placeholder={t.postalCode}
            value={addr.codigo_postal}
            onChange={(event) =>
              setAddr({
                ...addr,
                codigo_postal: event.target.value
              })
            }
          />

          <label className="check-line">
            <input
              type="checkbox"
              checked={addr.predeterminada}
              onChange={(event) =>
                setAddr({
                  ...addr,
                  predeterminada: event.target.checked
                })
              }
            />
            {t.defaultAddress}
          </label>

          <button className="btn-neon">
            {editingAddressId ? t.saveChanges : t.add}
          </button>

          {editingAddressId && (
            <button
              type="button"
              className="btn-ghost"
              onClick={cancelEditAddress}
            >
              {t.cancelEdit}
            </button>
          )}
        </form>

        <div className="simple-list">
          {addresses.map((address) => (
            <div className="simple-item" key={address.id}>
              <span>
                {address.calle}, {address.ciudad} ({address.departamento}){' '}
                {address.predeterminada && '★'}
              </span>

              <span className="row-actions">
                <button
                  className="btn-ghost"
                  onClick={() => editAddress(address)}
                >
                  {t.edit}
                </button>

                <button
                  className="btn-ghost"
                  onClick={() => delAddress(address.id)}
                >
                  {t.delete}
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-card">
        <h2>{t.orders}</h2>

        <form className="address-form" onSubmit={applyFilters}>
          <input
            className="input-m"
            type="date"
            value={filters.fecha_desde}
            onChange={(event) =>
              setFilters({
                ...filters,
                fecha_desde: event.target.value
              })
            }
          />

          <input
            className="input-m"
            type="date"
            value={filters.fecha_hasta}
            onChange={(event) =>
              setFilters({
                ...filters,
                fecha_hasta: event.target.value
              })
            }
          />

          <select
            className="input-m"
            value={filters.estado}
            onChange={(event) =>
              setFilters({
                ...filters,
                estado: event.target.value
              })
            }
          >
            <option value="">{t.orderAll}</option>
            <option value="pendiente">{t.orderPending}</option>
            <option value="procesando">{t.orderProcessing}</option>
            <option value="enviado">{t.orderShipped}</option>
            <option value="entregado">{t.orderDelivered}</option>
            <option value="cancelado">{t.orderCancelled}</option>
          </select>

          <button className="btn-outline-neon">{t.filter}</button>
        </form>

        <div className="simple-list">
          {orders.length === 0 ? (
            <div className="muted">{t.noRegisteredOrders}</div>
          ) : (
            orders.map((order) => (
              <div className="simple-item" key={order.id}>
                <span>
                  {order.numero} · {getTranslatedOrderStatus(t, order.estado)} ·
                  S/ {order.monto_total}
                </span>

                <span className="muted">
                  {new Date(order.fecha).toLocaleDateString()}
                </span>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="panel-card danger-zone">
        <h2>{t.deleteAccount}</h2>

        <form className="address-form" onSubmit={deleteAccount}>
          <input
            className="input-m"
            type="password"
            placeholder={t.deletePasswordPlaceholder}
            value={deletePassword}
            onChange={(event) => setDeletePassword(event.target.value)}
            required
          />

          <button className="btn-danger">{t.deleteForever}</button>
        </form>
      </section>
    </div>
  )
}