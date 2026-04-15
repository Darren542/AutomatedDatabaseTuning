import React, { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState("POC dashboard ready.")
  useEffect(() => {
    // Later: fetch recommendations from an API or load report artifacts.
    setStatus("POC dashboard: wire to API/report later.")
  }, [])

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
      <h1>SQL Server Autotuner (POC)</h1>
      <p>{status}</p>

      <h2>What this will show</h2>
      <ul>
        <li>Top index recommendations (CREATE INDEX)</li>
        <li>Why each recommendation was made (queries + metrics)</li>
        <li>Predicted vs actual improvement (after applying)</li>
      </ul>

      <h2>Next steps</h2>
      <ol>
        <li>Build a small API (optional) to serve recommendations</li>
        <li>Load feature store metrics and render charts</li>
      </ol>
    </div>
  )
}
