import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {dict} from '../src/i18n.js'
import {featureText} from '../src/featureText.js'
import {parseRoute,routeUrl,safeDestination,protectedPages} from '../src/navigation.js'
const root=fileURLToPath(new URL('../src/',import.meta.url))
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(p=>p.isDirectory()?files(path.join(dir,p.name)):[path.join(dir,p.name)])}

test('new UI translations exist in Spanish and English and all static t keys resolve',()=>{
  assert.deepEqual(Object.keys(featureText.es).sort(),Object.keys(featureText.en).sort())
  for(const p of files(root).filter(p=>/\.(jsx|js)$/.test(p))){
    const src=fs.readFileSync(p,'utf8')
    for(const [,key] of src.matchAll(/\bt\.([a-zA-Z][\w]*)/g)){
      assert.ok(dict.es[key]!==undefined,`${path.basename(p)}: missing es.${key}`)
      assert.ok(dict.en[key]!==undefined,`${path.basename(p)}: missing en.${key}`)
    }
  }
  for(const text of Object.values(featureText.es))assert.ok(!text.includes('?'),'Corrupt Spanish translation')
})
test('wishlist and safe auth destinations preserve internal navigation',()=>{
  assert.equal(parseRoute('/deseos').page,'wishlist');assert.equal(routeUrl('wishlist'),'/deseos');assert.ok(protectedPages.has('wishlist'))
  assert.equal(safeDestination('https://untrusted.invalid'),'/');assert.equal(safeDestination('//untrusted.invalid'),'/')
  assert.equal(safeDestination('/producto/1'),'/producto/1')
})
