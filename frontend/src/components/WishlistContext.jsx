import {createContext,useContext,useEffect,useState,useCallback} from 'react'
import {api,getApiError} from '../services/api'
const Context=createContext(null)
export const useWishlist=()=>useContext(Context)

export function WishlistProvider({user,children}) {
  const empty={items:[],saved_ids:[],notifications:[],count:0}
  const [data,setData]=useState(empty),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[page,setPage]=useState(1),[available,setAvailable]=useState(null)
  const load=useCallback(async signal=>{
    if(!user) {setData(empty);setAvailable(null);return}
    setLoading(true)
    try {const {data}=await api.get('/wishlist/',{params:{page},signal});if(!signal?.aborted){setData({...data,owner:user.id});setAvailable(true);setError('')}}
    catch(e){if(!signal?.aborted){if(e.response?.status===404){setData({...empty,owner:user.id});setAvailable(false);setError('')}else setError(getApiError(e))}}
    finally{if(!signal?.aborted)setLoading(false)}
  },[user?.id,page])
  useEffect(()=>{const c=new AbortController();load(c.signal);return()=>c.abort()},[load])
  useEffect(()=>{setPage(1);setError('');setAvailable(null)},[user?.id])
  useEffect(()=>{
    if(!user||available!==true)return
    const timer=setInterval(()=>{if(document.visibilityState==='visible')load()},120000)
    return()=>clearInterval(timer)
  },[load,available])
  const toggle=async id=>{
    if(busy||available===false)return
    setBusy(true);setError('')
    try {if((data.saved_ids||[]).includes(id)) await api.delete(`/wishlist/${id}/`);else await api.put(`/wishlist/${id}/`);if(page!==1)setPage(1);else await load()}
    catch(e){setError(getApiError(e))}finally{setBusy(false)}
  }
  const read=async id=>{try{await api.post(`/notifications/${id}/read/`);await load()}catch(e){setError(getApiError(e))}}
  return <Context.Provider value={{...(data.owner===user?.id?data:empty),available:data.owner===user?.id?available:null,error,busy,loading,page,setPage,toggle,read,load,user}}>{children}</Context.Provider>
}

export function WishButton({id,t,onNavigate}) {
  const w=useWishlist(),saved=w.saved_ids.includes(id)
  const label=w.available===false?t.wishlistUnavailable:saved?t.removeWish:t.saveWish
  return <button type="button" className={`wish-button ${saved?'saved':''}`} aria-pressed={saved} aria-label={label} title={label} disabled={w.busy||w.loading||w.available===false} onClick={()=>w.user?w.toggle(id):onNavigate('login',{next:window.location.pathname+window.location.search})}>{saved?'♥':'♡'}</button>
}
