import test from 'node:test'
import assert from 'node:assert/strict'
import { toRequest, testConnection, canSaveTarget } from './targets.js'

const form = { name: 'Demo', server: 'localhost', database: 'Demo', authentication: 'windows', username: 'private', password: 'secret', connection_timeout_seconds: '5', query_timeout_seconds: '6' }
test('Windows request omits credentials; numeric inputs become numbers', () => {
  const request = toRequest(form)
  assert.equal(request.connection_timeout_seconds, 5)
  assert.equal(request.query_timeout_seconds, 6)
  assert.equal('credentials' in request, false)
  assert.equal('password' in request, false)
})
test('SQL request preserves password whitespace only inside credentials', () => {
  const request = toRequest({ ...form, authentication: 'sql', password: ' secret ' })
  assert.deepEqual(request.credentials, { username: 'private', password: ' secret ' })
  assert.equal('password' in request, false)
})
test('failed connection with HTTP 200 remains a failure and ignores raw message', async () => {
  const result = await testConnection(form, undefined, async (url, options) => {
    assert.equal(url, '/api/v1/targets/test-connection')
    assert.equal(options.method, 'POST')
    return { ok: true, status: 200, json: async () => ({ connected: false, code: 'authentication_failed', message: 'secret' }) }
  })
  assert.equal(result.connected, false)
  assert.ok(!result.message.includes('secret'))
})
test('malformed, contradictory, and unknown responses are not treated as success', async () => {
  for (const body of [null, {}, { connected: true, code: 'timeout' }, { connected: false, code: 'connected' }, { connected: true, code: 'secret' }]) {
    await assert.rejects(testConnection(form, undefined, async () => ({ ok: true, status: 200, json: async () => body })), /unexpected response/)
  }
})
test('unreadable and validation responses do not disclose raw bodies', async () => {
  await assert.rejects(testConnection(form, undefined, async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('secret') } })), /unreadable response/)
  await assert.rejects(testConnection(form, undefined, async () => ({ ok: false, status: 422 })), /required fields/)
})
test('success uses the explicit connected flag', async () => {
  const result = await testConnection(form, undefined, async () => ({ ok: true, status: 200, json: async () => ({ connected: true, code: 'connected' }) }))
  assert.equal(result.connected, true)
})

test('elevated permissions require acknowledgement without bypassing readiness', () => {
  const ready={connected:true,collector_ready:true,ddl_restricted:false}
  assert.equal(canSaveTarget(ready),false)
  assert.equal(canSaveTarget(ready,true),true)
  assert.equal(canSaveTarget({...ready,collector_ready:false},true),false)
  assert.equal(canSaveTarget({...ready,connected:false},true),false)
  assert.equal(canSaveTarget({...ready,ddl_restricted:true}),true)
  assert.equal(canSaveTarget({...ready,ddl_restricted:true},false,true),false)
  assert.equal(canSaveTarget({...ready,ddl_restricted:true},true,true),true)
})
