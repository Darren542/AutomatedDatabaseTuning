import test from 'node:test'
import assert from 'node:assert/strict'
import { request, utcDate } from './client.js'

test('UTC repository timestamps never become browser-local instants', () => {
  assert.equal(utcDate('2026-10-12T12:00:00').toISOString(), '2026-10-12T12:00:00.000Z')
  assert.equal(utcDate('2026-10-12T05:00:00-07:00').toISOString(), '2026-10-12T12:00:00.000Z')
  assert.equal(utcDate(null), null)
})
test('failed repository responses never echo arbitrary server text', async () => {
  const original=globalThis.fetch
  globalThis.fetch=async()=>({ok:false,status:503,text:async()=> 'PWD=secret'})
  try { await assert.rejects(request('/targets'), /repository is unavailable/i) }
  finally {globalThis.fetch=original}
})
test('collection payload is sent as JSON to the versioned endpoint', async () => {
  const original=globalThis.fetch
  globalThis.fetch=async(url,options)=>{
    assert.equal(url,'/api/v1/collections')
    assert.equal(options.method,'POST')
    assert.equal(JSON.parse(options.body).force_metadata,true)
    return {ok:true,json:async()=>({batch_id:'test',status:'Pending'})}
  }
  try { assert.equal((await request('/collections',{method:'POST',body:{force_metadata:true}})).status,'Pending') }
  finally {globalThis.fetch=original}
})

test('cancelling response-body parsing remains an abort instead of a UI error', async () => {
  const original=globalThis.fetch
  const aborted=Object.assign(new Error('Cancelled'),{name:'AbortError'})
  globalThis.fetch=async()=>({ok:true,json:async()=>{throw aborted}})
  try { await assert.rejects(request('/candidate-sets'),{name:'AbortError'}) }
  finally {globalThis.fetch=original}
})
