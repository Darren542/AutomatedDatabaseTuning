import React, { useEffect, useRef, useState } from 'react'
import { request, dateLabel } from '../api/client.js'

export default function CandidateGenerator({ targetId, batches, initialBatchId, initialSetId, onScore, onCollection, revision }) {
  const [batchId,setBatchId]=useState(initialBatchId || '')
  const [sets,setSets]=useState([]), [set,setSet]=useState(null)
  const [selected,setSelected]=useState([]), [action,setAction]=useState(''), [error,setError]=useState(''), [busy,setBusy]=useState(false)
  const [readiness,setReadiness]=useState(null)
  const mounted=useRef(true)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
  useEffect(()=>{
    const c=new AbortController()
    setBatchId(initialBatchId || '');setSet(null);setError('')
    request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`,{signal:c.signal}).then(async rows=>{
      setSets(rows)
      const item=rows.find(s=>s.candidate_set_id===initialSetId) || (!initialBatchId ? rows[0] : null)
      if(item){const result=await request(`/candidate-sets/${item.candidate_set_id}`,{signal:c.signal});if(!c.signal.aborted)show(result)}
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[targetId,initialBatchId,initialSetId])
  useEffect(()=>{
    const c=new AbortController();setReadiness(null)
    if(batchId)request(`/candidate-sets/eligibility/${batchId}`,{signal:c.signal}).then(setReadiness).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[batchId])
  useEffect(()=>{
    if(!revision)return
    const c=new AbortController()
    request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`,{signal:c.signal}).then(setSets).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[revision,targetId])
  function show(result){setSet(result);setBatchId(result.batch_id.toLowerCase());setSelected(result.recommendations.map(r=>r.recommendation_id))}
  async function generate(){
    setBusy(true);setError('')
    try{
      const result=await request('/candidate-sets',{method:'POST',body:{batch_id:batchId},errors:{422:'This collection needs successful runtime, usage, operational, missing-index and source components plus fresh metadata. Collect again with Force metadata refresh.'}})
      if(!mounted.current)return
      show(result);setSets(await request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`))
    }catch(e){if(mounted.current)setError(e.message)}finally{if(mounted.current)setBusy(false)}
  }
  async function open(id){setBusy(true);setError('');try{show(await request(`/candidate-sets/${id}`))}catch(e){setError(e.message)}finally{setBusy(false)}}
  const eligible=batches.filter(b=>['Completed','Partial'].includes(b.status)&&(!targetId||b.target_id.toLowerCase()===targetId.toLowerCase()))
  const rows=(set?.recommendations || []).filter(r=>!action || r.action===action)
  function toggle(id){setSelected(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id])}
  return <div className="workflow-page">
    <section className="card"><div className="card-head"><div><h2>Discover index shapes</h2><p>Choose stored workload evidence. Review coverage, keys and includes before scoring.</p></div><span className="badge">Step 3 · Discovery</span></div><div className="card-body analysis-controls">
      <label className="field"><span>Source collection</span><select aria-label="Candidate source collection" value={batchId} disabled={busy} onChange={e=>{setBatchId(e.target.value);setSet(null);setSelected([])}}><option value="">Select a collection</option>{eligible.map(b=><option key={b.batch_id} value={b.batch_id}>{b.label || b.batch_id.slice(0,8)} · {dateLabel(b.created_at_utc)}</option>)}</select></label>
      <button disabled={busy || !batchId || !readiness?.eligible} onClick={generate}>{busy?'Discovering…':'Generate candidate set'}</button><button className="secondary" disabled={!batchId} onClick={()=>onCollection(batchId)}>View source collection</button>
    </div></section>
    {readiness&&<p className={`notice ${readiness.eligible?'success':'warning'}`}>{readiness.message}{readiness.eligible&&` ${readiness.missing_index_hints} missing-index hints · ${readiness.existing_indexes} index definitions. ${readiness.has_baseline?'A prior observation is available; reset/definition checks still apply.':'No prior observation: unused-index DROP advice will be withheld.'}`}</p>}
    {error&&<p className="notice error" role="alert">{error}</p>}
    {!!sets.length&&<label className="field"><span>Saved candidate set</span><select aria-label="Saved candidate set" value={set?.candidate_set_id || ''} disabled={busy} onChange={e=>open(e.target.value)}><option value="">Select a saved candidate set</option>{sets.map(s=><option key={s.candidate_set_id} value={s.candidate_set_id}>{dateLabel(s.created_at_utc)} · collection {s.batch_id.slice(0,8)} · set {s.candidate_set_id.slice(0,8)}</option>)}</select></label>}
    {!set?<div className="card empty"><h3>Select a workload collection</h3><p>Discovery creates a frozen candidate set. It does not rank opportunities or calculate weighted scores.</p></div>:<>
      <div className="metrics">{['CREATE','RETAIN','DROP'].map(a=><div className="metric" key={a}><span>{a} shapes</span><strong>{set.recommendations.filter(r=>r.action===a).length}</strong></div>)}<div className="metric"><span>Rejected evidence shapes</span><strong>{set.diagnostics.length}</strong></div></div>
      <section className="card"><div className="card-head"><div><h2>Review candidate set</h2><p>{selected.length} selected · evidence observed {dateLabel(set.observed_at_utc)}</p></div><button disabled={!selected.length} onClick={()=>onScore(set.candidate_set_id,selected,set.batch_id)}>Continue to scoring →</button></div>
        <div className="card-body actions"><label>Action <select aria-label="Candidate action" value={action} onChange={e=>setAction(e.target.value)}><option value="">All actions</option>{['CREATE','RETAIN','DROP'].map(a=><option key={a}>{a}</option>)}</select></label><button className="secondary" onClick={()=>setSelected(set.recommendations.map(r=>r.recommendation_id))}>Select all</button><button className="secondary" onClick={()=>setSelected([])}>Clear selection</button></div>
        <div className="table-scroll"><table><thead><tr><th>Include</th><th>Action</th><th>Object / index</th><th>Key columns</th><th>Include columns</th><th>Evidence</th></tr></thead><tbody>{rows.map(r=><tr key={r.recommendation_id}><td><input type="checkbox" aria-label={`Include ${r.index_name}`} checked={selected.includes(r.recommendation_id)} onChange={()=>toggle(r.recommendation_id)}/></td><td><strong>{r.action}</strong><small>{r.protected?'Protected':r.action==='CREATE'?'Unscored':'Rule-based'}</small></td><td><strong>{r.schema_name}.{r.table_name}</strong><small>{r.index_name}</small></td><td>{r.key_columns.join(', ')}</td><td>{r.included_columns.join(', ') || 'None'}</td><td><details><summary>Inspect {r.index_name}</summary><p>{r.rationale}</p><pre className="sql-preview">{r.sql || '-- RETAIN: no structural change proposed.'}</pre><p>{r.source_evidence.length} source references · {r.affected_queries.length} textual query associations</p>{r.usage_evidence&&<p>Usage observations: {JSON.stringify(r.usage_evidence)}</p>}<ul>{r.warnings.map(w=><li key={w}>{w}</li>)}</ul></details></td></tr>)}</tbody></table></div>
        {!rows.length&&<p className="card-body">No candidates match this action. Missing-index evidence may legitimately contain no opportunities.</p>}
      </section>
      <p className="hint">Set {set.candidate_set_id} · Collection {set.batch_id} · Metadata {set.metadata_batch_id} · Input hash {set.input_hash}. Scoring uses this exact snapshot. Changes to the target require a new collection and candidate set.</p>
      {!!set.diagnostics.length&&<details className="card card-body"><summary>Rejected evidence shapes</summary><pre className="evidence-json">{JSON.stringify(set.diagnostics,null,2)}</pre></details>}
    </>}
  </div>
}
