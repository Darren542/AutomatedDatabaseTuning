import React, { useState } from 'react'
import { request } from '../api/client.js'
import { canSaveTarget } from '../api/targets.js'

const initial = { name: '', server: 'localhost\\SQLEXPRESS', database: 'WideWorldImporters', authentication: 'windows', driver: 'ODBC Driver 18 for SQL Server', encrypt: true, trust_server_certificate: false, connection_timeout_seconds: 5, query_timeout_seconds: 30, username: '', password: '', credential_reference: '' }
const results = {
  connected: 'Connection and collector permissions validated.',
  insufficient_permissions: 'Connected, but some required telemetry sources are inaccessible. Review the capability checks below.',
  excessive_permissions: 'Connected, but this account can alter database objects. A restricted account is recommended. You can acknowledge this warning and continue.',
  connection_failed: 'Could not connect. Check the instance and certificate settings.',
  authentication_failed: 'Authentication failed. Check the account and database access.',
  driver_unavailable: 'Install the selected ODBC driver on the API machine.',
  timeout: 'The connection test timed out.', database_unavailable: 'The database is unavailable or inaccessible.',
  validation_failed: 'Could not validate database access.', invalid_configuration: 'Check the connection configuration.',
}

export default function TargetForm({ onSaved, close }) {
  const [form, setForm] = useState(initial)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)
  const [saveWarning, setSaveWarning] = useState(false)
  const permissionWarning = saveWarning || (result?.connected === true && result.ddl_restricted === false)
  function change(event) {
    const { name, value, checked, type } = event.target
    setForm(current => ({ ...current, [name]: type === 'checkbox' ? checked : value,
      ...(name === 'authentication' ? { username: '', password: '', credential_reference: '' } : {}) }))
    setResult(null); setError(''); setAcknowledged(false); setSaveWarning(false)
  }
  const config = () => {
    const { username, password, credential_reference, ...target } = form
    return { ...target, connection_timeout_seconds: Number(target.connection_timeout_seconds), query_timeout_seconds: Number(target.query_timeout_seconds) }
  }
  async function test(event) {
    event.preventDefault(); setBusy('test'); setError(''); setResult(null); setAcknowledged(false); setSaveWarning(false)
    try {
      setResult(await request('/targets/test-connection', { method: 'POST', body: { ...config(),
        ...(form.authentication === 'sql' ? { credentials: { username: form.username, password: form.password } } : {}) } }))
    } catch (e) { setError(e.message) }
    finally { setBusy(''); setForm(current => ({ ...current, password: '' })) }
  }
  async function save() {
    setBusy('save'); setError('')
    try {
      const target = await request('/targets', { method: 'POST', body: { ...config(), acknowledge_excessive_permissions: acknowledged, credential_reference: form.authentication === 'sql' ? form.credential_reference : null }, errors: { 428: 'The account used for saving can alter database objects. Acknowledge the permission warning below to continue.' } })
      onSaved(target)
    } catch (e) { if (e.status === 428) { setSaveWarning(true); setAcknowledged(false) } setError(e.message) } finally { setBusy('') }
  }
  const input = (name, extra = {}) => <input id={name} name={name} value={form[name]} onChange={change} required {...extra} />
  const field = (name, label, extra = {}) => <label className="field" htmlFor={name}><span>{label}</span>{input(name, extra)}</label>
  return <section className="card target-form"><div className="card-head"><div><h2>Add a database target</h2><p>Test access, then save the connection metadata.</p></div><button className="text-button" onClick={close} disabled={!!busy}>Close</button></div>
    <form onSubmit={test}><fieldset disabled={!!busy}>
      {field('name', 'Target name', { maxLength: 200, placeholder: 'e.g. WWI collector' })}
      <div className="form-grid">{field('server', 'SQL Server instance')}{field('database', 'Database')}</div>
      <label className="field"><span>Authentication</span><select name="authentication" value={form.authentication} onChange={change}><option value="windows">Windows authentication</option><option value="sql">SQL Server authentication</option></select></label>
      {form.authentication === 'sql' && <><div className="form-grid">{field('username', 'Username', { autoComplete: 'off' })}{field('password', 'Password', { type: 'password', autoComplete: 'new-password' })}</div>{field('credential_reference', 'Credential reference', { placeholder: 'WWI_COLLECTOR' })}<p className="hint">Saving uses the server-configured reference. Passwords are cleared after testing and never saved in target metadata.</p></>}
      <div className="checks"><label><input type="checkbox" name="encrypt" checked={form.encrypt} onChange={change} /> Encrypt connection</label><label><input type="checkbox" name="trust_server_certificate" checked={form.trust_server_certificate} onChange={change} /> Trust server certificate</label></div>
      <p className="hint">Enable certificate trust for the local SQLEXPRESS demo if it uses a self-signed certificate. Windows authentication uses the API process account.</p>
      <details><summary>Advanced settings</summary><label className="field"><span>ODBC driver</span><select name="driver" value={form.driver} onChange={change}><option>ODBC Driver 18 for SQL Server</option><option>ODBC Driver 17 for SQL Server</option></select></label><div className="form-grid">{field('connection_timeout_seconds', 'Connection timeout (seconds)', { type: 'number', min: 1, max: 60 })}{field('query_timeout_seconds', 'Query timeout (seconds)', { type: 'number', min: 1, max: 60 })}</div></details>
    </fieldset>
      <div aria-live="polite">{error && <p className="notice error" role="alert">{error}</p>}{result && <div className={`notice ${result.collector_ready && !permissionWarning ? 'success' : 'warning'}`}><strong>{result.collector_ready ? (permissionWarning ? 'Ready to collect · permission warning' : 'Ready to collect') : result.connected ? 'Connected · setup needed' : 'Connection failed'}</strong><p>{results[result.code] || 'Review the connection configuration.'}</p><div className="capabilities">{[['query_store_readable', 'Query Store'], ['index_usage_readable', 'Index usage'], ['index_operational_readable', 'Operational stats'], ['missing_indexes_readable', 'Missing indexes'], ['source_state_readable', 'Source state'], ['metadata_readable', 'Metadata'], ['ddl_restricted', 'DDL restricted']].map(([key, label]) => <span key={key}>{result[key] ? '✓' : '×'} {label}</span>)}</div></div>}</div>
      {permissionWarning && <div className="notice warning"><p>This account can alter database objects. A restricted account is recommended. Continuing keeps the account's existing privileges.</p><label className="check"><input type="checkbox" checked={acknowledged} disabled={!!busy} onChange={e=>{setAcknowledged(e.target.checked);setError('')}}/>I understand the elevated permissions and want to use this connection anyway.</label></div>}
      <div className="actions"><button disabled={!!busy}>{busy === 'test' ? 'Testing…' : 'Test connection'}</button><button className="secondary" type="button" onClick={save} disabled={!!busy || !canSaveTarget(result, acknowledged, saveWarning)}>{busy === 'save' ? 'Saving…' : 'Save target'}</button></div>
    </form></section>
}
