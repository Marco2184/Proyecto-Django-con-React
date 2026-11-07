import {lazy,Suspense,useRef,useState} from 'react'
import {chatText} from '../chatText'
import '../styles/chat.css'
const ChatPanel=lazy(()=>import('./ChatPanel'))
export default function ChatLauncher(props) {
  const [open,setOpen]=useState(false), [started,setStarted]=useState(false)
  const launcher=useRef(null), text=chatText[props.lang]
  return <>
    <button ref={launcher} className="monolith-chat-launcher" onClick={()=>{setStarted(true);setOpen(true)}} aria-label={text.open} aria-haspopup="dialog" aria-expanded={open}>
      <span aria-hidden="true">◈</span><span>{text.title}</span>
    </button>
    {started && <Suspense fallback={<div className="monolith-chat-loading" role="status">{text.loading}</div>}>
      <ChatPanel {...props} open={open} onClose={()=>{setOpen(false);launcher.current?.focus()}} />
    </Suspense>}
  </>
}
