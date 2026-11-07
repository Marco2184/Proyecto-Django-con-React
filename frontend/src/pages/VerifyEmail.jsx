import { getTranslatedText } from '../i18n'
import { useEffect, useRef, useState } from 'react'
import { api, getApiError } from '../services/api'

export default function VerifyEmail({ t, token, onNavigate, onVerified }) {
  const pending=useRef(null)
  const [state, setState] = useState({ loading: true, msg: '', error: '' })
  useEffect(() => {
    let active=true
    if(!pending.current||pending.current.token!==token)pending.current={token,promise:api.post(`/auth/verify/${token}/`)}
    pending.current.promise.then(({data})=>{if(active){setState({loading:false,msg:data.message,error:''});onVerified?.()}}).catch(err=>{if(active)setState({loading:false,msg:'',error:getApiError(err)})})
    return()=>{active=false}
  }, [token])
  return <div className="panel-page narrow"><div className="section-tag">{t.verifyTag}</div><h1>{t.verifyTitle}</h1>{state.loading && <div className="loading-m">{t.verifying}</div>}{state.msg && <div className="alert success">{getTranslatedText(t, state.msg)}</div>}{state.error && <div className="alert error">{getTranslatedText(t, state.error)}</div>}<button className="btn-neon" onClick={()=>onNavigate('login')}>{t.goToLogin}</button></div>
}
