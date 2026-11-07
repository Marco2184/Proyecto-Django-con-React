import { useEffect, useState } from 'react'
export default function ProductImage({src,alt,className='',onError,...props}) {
  const [failed,setFailed] = useState(false)
  useEffect(()=>setFailed(false),[src])
  return src && !failed ? <img src={src} alt={alt} loading="lazy" decoding="async" width="480" height="300" {...props} className={`product-image ${className}`} onError={event=>{setFailed(true);onError?.(event)}} /> :
    <span className={`prod-img-placeholder ${className}`} role="img" aria-label={alt}>MONOLITH</span>
}
