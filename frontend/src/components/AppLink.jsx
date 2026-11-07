import { routeUrl } from '../navigation'
export default function AppLink({page,payload,onNavigate,children,...props}) {
  return <a href={routeUrl(page,payload)} {...props} onClick={event=>{
    if (event.button!==0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault(); onNavigate(page,payload)
  }}>{children}</a>
}
