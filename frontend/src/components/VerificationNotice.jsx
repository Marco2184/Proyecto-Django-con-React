import { useState } from 'react'
import { api, getApiError } from '../services/api'

export default function VerificationNotice({user,onUser,t}) {
  const [busy,setBusy]=useState(false),[status,setStatus]=useState('')
  if (!user || user.email_verificado) return null
  const run=async resend=>{
    if(busy) return
    setBusy(true);setStatus('')
    try {
      if(resend) {await api.post('/auth/resend-verification/');setStatus(t.verificationSent)}
      else {const {data}=await api.get('/auth/me/');onUser(data);if(!data.email_verificado)setStatus(t.verificationPending)}
    } catch(e){setStatus(getApiError(e))} finally{setBusy(false)}
  }
  return <aside className="alert warn verification-notice" role="status"><span>{t.verificationPending}</span><button className="btn-ghost" disabled={busy} onClick={()=>run(true)}>{t.resendVerification}</button><button className="btn-ghost" disabled={busy} onClick={()=>run(false)}>{t.refreshStatus}</button>{status && <p>{status}</p>}</aside>
}
