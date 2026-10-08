import React, { useEffect, useRef, useState } from 'react'
import { testConnection } from './api/targets.js'
import './styles.css'

const initial = {
  name: 'Local demo', server: 'localhost\\SQLEXPRESS', database: 'WideWorldImporters',
  authentication: 'windows', username: '', password: '',
  driver: 'ODBC Driver 18 for SQL Server', encrypt: true,
  trust_server_certificate: false, connection_timeout_seconds: 5, query_timeout_seconds: 5,
}

function Field({ label, id, children, hint }) {
  return <div className="field"><label htmlFor={id}>{label}</label>{children}
    {hint && <small id={`${id}-hint`}>{hint}</small>}</div>
}

export default function App() {
  const [form, setForm] = useState(initial)
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const active = useRef(null)
  useEffect(() => () => active.current?.abort(), [])

  function change(event) {
    const { name, value, type, checked } = event.target
    setStatus(null)
    setForm(current => ({ ...current, [name]: type === 'checkbox' ? checked : value,
      ...(name === 'authentication' ? { username: '', password: '' } : {}) }))
  }

  async function submit(event) {
    event.preventDefault()
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setBusy(true)
    setStatus(null)
    const timer = setTimeout(() => controller.abort(), 125000)
    try {
      const result = await testConnection(form, controller.signal)
      if (!controller.signal.aborted) setStatus({ kind: result.connected ? 'success' : 'error', message: result.message })
    } catch (error) {
      setStatus({ kind: 'error', message: error.name === 'AbortError'
        ? 'The request timed out. Check that the API is running and try again.'
        : error instanceof TypeError ? 'Cannot reach the API. Start the backend and try again.' : error.message })
    } finally {
      clearTimeout(timer)
      active.current = null
      setBusy(false)
      setForm(current => ({ ...current, password: '' }))
    }
  }

  function input(name, options = {}) {
    return <input id={name} name={name} value={form[name]} onChange={change} required {...options} />
  }

  return <div className="app">
    <header className="topbar"><a className="brand" href="/"> <span className="brand-mark" aria-hidden="true">≋</span> Database Tuner</a><span className="workspace">Local workspace</span></header>
    <main>
      <div className="page-heading"><p className="eyebrow">DATABASE CONNECTION</p><h1>Configure a target</h1><p>Connect to SQL Server to begin understanding your workload.</p></div>
      <div className="layout">
        <section className="panel" aria-labelledby="connection-heading">
          <div className="panel-heading"><h2 id="connection-heading">Connection details</h2><p>Enter the instance and database you want to inspect.</p></div>
          <form onSubmit={submit}>
            <fieldset disabled={busy}>
              <Field label="Target name" id="name">{input('name', { maxLength: 200 })}</Field>
              <div className="grid">
                <Field label="SQL Server instance" id="server" hint="Use the exact instance name shown in SSMS.">{input('server', { 'aria-describedby': 'server-hint' })}</Field>
                <Field label="Database" id="database">{input('database')}</Field>
              </div>
              <Field label="Authentication" id="authentication" hint={form.authentication === 'windows' ? 'Uses the Windows account running the backend.' : 'Credentials are used only for this connection test.'}>
                <select id="authentication" name="authentication" value={form.authentication} onChange={change} aria-describedby="authentication-hint"><option value="windows">Windows authentication</option><option value="sql">SQL Server authentication</option></select>
              </Field>
              {form.authentication === 'sql' && <div className="grid">
                <Field label="Username" id="username">{input('username', { autoComplete: 'off' })}</Field>
                <Field label="Password" id="password" hint="Cleared after each test.">{input('password', { type: 'password', autoComplete: 'new-password', 'aria-describedby': 'password-hint' })}</Field>
              </div>}
              <div className="security">
                <label className="check"><input type="checkbox" name="encrypt" checked={form.encrypt} onChange={change} /> Encrypt connection</label>
                <label className="check"><input type="checkbox" name="trust_server_certificate" checked={form.trust_server_certificate} onChange={change} aria-describedby="certificate-hint" /> Trust server certificate</label>
                <small id="certificate-hint">For this local SQLEXPRESS demo, enable certificate trust to match your working connection.</small>
              </div>
              <details><summary>Advanced connection settings</summary><div className="advanced">
                <Field label="ODBC driver" id="driver"><select id="driver" name="driver" value={form.driver} onChange={change}><option>ODBC Driver 18 for SQL Server</option><option>ODBC Driver 17 for SQL Server</option></select></Field>
                <div className="grid"><Field label="Connection timeout (seconds)" id="connection_timeout_seconds">{input('connection_timeout_seconds', { type: 'number', min: 1, max: 60, step: 1 })}</Field><Field label="Query timeout (seconds)" id="query_timeout_seconds">{input('query_timeout_seconds', { type: 'number', min: 1, max: 60, step: 1 })}</Field></div>
              </div></details>
            </fieldset>
            <div className="actions"><button type="submit" disabled={busy}>{busy ? 'Testing connection…' : 'Test connection'}<span aria-hidden="true"> →</span></button><span>This test does not save the target.</span></div>
            <div aria-live="polite" aria-atomic="true">
              {busy && <p className="result pending" role="status">Connecting to SQL Server…</p>}
              {status && <div className={`result ${status.kind}`} role={status.kind === 'error' ? 'alert' : 'status'}><strong>{status.kind === 'success' ? 'Connected' : 'Connection not verified'}</strong><p>{status.message}</p></div>}
            </div>
          </form>
        </section>
        <aside><p className="eyebrow">GETTING CONNECTED</p><h2>A familiar starting point</h2><p>Use the same instance, database, and authentication method you use in SQL Server Management Studio.</p><ol><li>Check your connection details.</li><li>Test access to the database.</li><li>Review the connection result.</li></ol><div className="aside-note"><h3>What this test does</h3><p>Opens a connection, verifies database access, and closes it. Your database data stays unchanged.</p></div><p className="muted">Saving targets and workload collection are coming in the next steps.</p></aside>
      </div>
    </main><footer>Automated Database Tuner <span>SQL Server · Sprint 1</span></footer>
  </div>
}
