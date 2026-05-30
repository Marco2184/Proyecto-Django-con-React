import { useEffect, useState } from 'react'
import { api, getApiError } from '../services/api'

export default function VerifyEmail({ token, onNavigate }) {
  const [state, setState] = useState({ loading: true, msg: '', error: '' })
  useEffect(() => {
    api.post(`/auth/verify/${token}/`).then(({data}) => setState({ loading:false, msg:data.message, error:'' })).catch(err => setState({ loading:false, msg:'', error:getApiError(err) }))
  }, [token])
  return <div className="panel-page narrow"><div className="section-tag">Email // Verification</div><h1>VERIFY EMAIL</h1>{state.loading && <div className="loading-m">VERIFYING...</div>}{state.msg && <div className="alert success">{state.msg}</div>}{state.error && <div className="alert error">{state.error}</div>}<button className="btn-neon" onClick={()=>onNavigate('login')}>Ir a login</button></div>
}
