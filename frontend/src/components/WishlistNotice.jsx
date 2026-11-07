import {useWishlist} from './WishlistContext'
export default function WishlistNotice({t,onNavigate}) {
  const w=useWishlist()
  return <>{w.error&&<p className="alert error" role="alert">{w.error}</p>}{w.notifications.length>0&&<aside className="alert success" role="status"><button className="link-neon" onClick={()=>onNavigate('wishlist')}>{t.priceDrops}: {w.notifications.length}</button></aside>}</>
}
