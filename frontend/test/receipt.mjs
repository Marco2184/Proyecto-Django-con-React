import assert from 'node:assert/strict'
import {inflateSync} from 'node:zlib'

export const cents=value=>Math.round(Number(value)*100)

function ascii85(value){
  const text=value.replace(/\s/g,'').replace(/^<~/,'').replace(/~>$/,'')
  const bytes=[];let group=[]
  const emit=(digits,count=4)=>{
    let number=digits.reduce((n,d)=>n*85+d,0)
    const block=[(number>>>24)&255,(number>>>16)&255,(number>>>8)&255,number&255]
    bytes.push(...block.slice(0,count))
  }
  for(const char of text){
    if(char==='z'){assert.equal(group.length,0);bytes.push(0,0,0,0);continue}
    const digit=char.charCodeAt(0)-33;assert.ok(digit>=0&&digit<85)
    group.push(digit);if(group.length===5){emit(group);group=[]}
  }
  if(group.length){const count=group.length-1;while(group.length<5)group.push(84);emit(group,count)}
  return Buffer.from(bytes)
}

export function receiptText(pdf){
  assert.ok(pdf.subarray(0,5).equals(Buffer.from('%PDF-')),'Receipt must be a real PDF')
  const source=pdf.toString('latin1'),parts=[]
  for(const match of source.matchAll(/stream\r?\n([\s\S]*?)\r?\n?endstream/g)){
    const header=source.slice(Math.max(0,source.lastIndexOf('obj',match.index)),match.index)
    if(!header.includes('FlateDecode'))continue
    let data=Buffer.from(match[1].replace(/[\r\n]+$/,''),'latin1')
    if(header.includes('ASCII85Decode'))data=ascii85(data.toString('ascii'))
    const content=inflateSync(data).toString('latin1')
    for(const literal of content.matchAll(/\(((?:\\[\s\S]|[^\\()])*)\)\s*Tj/g)){
      parts.push(literal[1].replace(/\\([0-7]{1,3}|[\s\S])/g,(_,escaped)=>/^[0-7]+$/.test(escaped)?String.fromCharCode(parseInt(escaped,8)):({n:'\n',r:'\r',t:'\t',b:'\b',f:'\f'}[escaped]??escaped)))
    }
  }
  return parts.join(' ').replace(/\s+/g,' ')
}

export function assertReceiptTotals(pdf,{subtotal,discount,total}){
  const text=receiptText(pdf)
  const amountAfter=label=>{
    const index=text.indexOf(label);assert.ok(index>=0,`Receipt label missing: ${label}`)
    const match=text.slice(index+label.length).match(/^\s*(-\s*)?S\/\s*(\d+\.\d{2})/)
    assert.ok(match,`Receipt amount missing: ${label}`)
    return cents(match[2])
  }
  assert.equal(amountAfter('Subtotal:'),cents(subtotal))
  if(cents(discount)>0)assert.equal(amountAfter('Descuento aplicado:'),cents(discount))
  assert.equal(amountAfter('Total:'),cents(total))
  const tax=cents(total)*18/118
  assert.equal(amountAfter('IGV incluido (18%):'),Math.round(tax),'IGV must be included in the paid total, not added a second time')
  assert.equal(cents(subtotal)-cents(discount),cents(total))
}
