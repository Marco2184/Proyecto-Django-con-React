import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {imageOf} from '../src/services/productImage.js'

const originalCovers = JSON.parse(fs.readFileSync(new URL('../../productos/covers.json', import.meta.url), 'utf8'))
const covers = JSON.parse(fs.readFileSync(new URL('../src/services/covers.json', import.meta.url), 'utf8'))

function legacyProduct(cover) {
  return {id:cover.product_id,nombre:cover.name,slug:cover.slug,
    imagen_url:cover.replaces_url,imagen_principal:`http://localhost:8000/media/${cover.replaces_file}`}
}

test('only TES VI overrides the published artwork, preserving every product identity',()=>{
  assert.equal(covers.length,originalCovers.length)
  for(const cover of covers){
    const original=originalCovers.find(c=>c.product_id===cover.product_id)
    assert.ok(original)
    if(cover.product_id===11){
      for(const key of ['product_id','name','slug','replaces_url','replaces_file'])assert.equal(cover[key],original[key])
      assert.ok(cover.url.startsWith('/covers/'))
    }else assert.deepEqual(cover,original)
  }
})

test('all 20 covers work with the old Django response and without portada',()=>{
  assert.equal(covers.filter(c=>c.url).length,20)
  for(const cover of covers) assert.equal(imageOf(legacyProduct(cover)),cover.url,cover.name)
})

test('the local TES VI image exists and takes priority over an empty legacy cover',()=>{
  for(const cover of covers.filter(c=>c.product_id===11)){
    const bytes=fs.readFileSync(new URL('../public'+cover.url,import.meta.url))
    assert.ok(bytes.length>100)
    const jpeg=bytes[0]===0xff&&bytes[1]===0xd8
    const png=bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))
    assert.ok(jpeg||png,'Expected a real image file, not an HTML error response')
    assert.equal(imageOf({...legacyProduct(cover),portada:{url:''}}),cover.url)
  }
})

test('similar names, different editions and administrator changes are preserved',()=>{
  const cover=covers.find(c=>c.product_id===25),product=legacyProduct(cover)
  for(const changes of [{id:9999},{nombre:'The Last of Us Part I'},{slug:'the-last-of-us-part-i'},
    {imagen_url:'https://example.invalid/manual.jpg'},{imagen_principal:'/media/productos/manual.jpg'}]){
    const changed={...product,...changes}
    assert.equal(imageOf(changed),changed.imagen_url)
  }
})

test('catalog, cart and wishlist use the shared canonical cover',()=>{
  assert.equal(imageOf({portada:{url:'https://example.invalid/official.jpg'},imagen_url:'wrong.jpg',imagen_principal:'wrong-file.jpg'}),'https://example.invalid/official.jpg')
})

test('an explicitly unavailable cover never falls back to unrelated artwork',()=>{
  assert.equal(imageOf({portada:{url:'',kind:'unavailable'},imagen_url:'wrong.jpg',imagen_principal:'wrong-file.jpg'}),'')
})

test('unlisted products and older API responses retain their images',()=>{
  assert.equal(imageOf({imagen_url:'external.jpg',imagen_principal:'uploaded.jpg'}),'external.jpg')
  assert.equal(imageOf({imagen_principal:'uploaded.jpg'}),'uploaded.jpg')
  assert.equal(imageOf(null),'')
})
