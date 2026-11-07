import { catalogApi } from './api'
let metadata, expiry = 0
async function allPages(path) {
  let page=1, results=[], data
  do {
    ;({data}=await catalogApi.get(path,{params:{page}}))
    results.push(...(data.results || data)); page++
  } while (data.next && page<=100)
  return results
}
export function catalogMetadata(reset=false) {
  if (reset || Date.now()>expiry) metadata=null
  if (!metadata) {
    expiry=Date.now()+300000
    metadata=Promise.all([allPages('/plataformas/'),allPages('/categorias/')]).catch(error=>{metadata=null; throw error})
  }
  return metadata
}
