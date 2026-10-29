import React, { useEffect, useState } from 'react'
import { request, dateLabel, number } from '../api/client.js'
import { filterRecommendations, scoreNumber } from '../api/recommendations.js'

export default function ScoringEngine({ targetId, context, onReview, onCollection, revision }) {
  const [sets,setSets]=useState([]),[setId,setSetId]=useState(context?.id || ''),[candidateSet,setCandidateSet]=useState(null)
  const [selected,setSelected]=useState([]),[weights,setWeights]=useState({read_weight:1,write_weight:1,storage_weight:.1})
  const [runs,setRuns]=useState([]),[analysis,setAnalysis]=useState(null),[compare,setCompare]=useState(null)
  const [detailId,setDetailId]=useState(''),[action,setAction]=useState(''),[status,setStatus]=useState(''),[search,setSearch]=useState('')
  const [legacy,setLegacy]=useState([]),[legacyId,setLegacyId]=useState('')
  const [error,setError]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>{
    const c=new AbortController()
    request(`/recommendations/analyses?limit=100${targetId?`&target_id=${targetId}`:''}`,{signal:c.signal}).then(rows=>setLegacy(rows.filter(r=>!r.candidate_set_id))).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`,{signal:c.signal}).then(rows=>{setSets(rows);setSetId(context?.id || rows[0]?.candidate_set_id || '')}).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[targetId,context?.id])
  useEffect(()=>{
    const c=new AbortController();setAnalysis(null);setCompare(null);setError('');setCandidateSet(null);setRuns([])
    if(!setId)return()=>c.abort()
    Promise.all([request(`/candidate-sets/${setId}`,{signal:c.signal}),request(`/recommendations/analyses?candidate_set_id=${setId}&limit=100${targetId?`&target_id=${targetId}`:''}`,{signal:c.signal})]).then(async([set,history])=>{
      setCandidateSet(set);setSelected(context?.id===setId&&context.ids?context.ids:set.recommendations.map(r=>r.recommendation_id))
      const matching=history.filter(a=>a.candidate_set_id?.toLowerCase()===setId.toLowerCase());setRuns(matching)
      const initialAnalysis=context?.id===setId&&context.analysisId?context.analysisId:matching[0]?.analysis_id
      if(initialAnalysis){const result=await request(`/recommendations/analyses/${initialAnalysis}`,{signal:c.signal});if(!c.signal.aborted)setAnalysis(result)}
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[setId,targetId])
  useEffect(()=>{
    if(!revision)return
    const c=new AbortController()
    request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`,{signal:c.signal}).then(setSets).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    if(setId)request(`/recommendations/analyses?candidate_set_id=${setId}&limit=100`,{signal:c.signal}).then(setRuns).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>c.abort()
  },[revision,targetId,setId])
  async function score(){setBusy(true);setError('');try{
    const result=await request('/recommendations/score',{method:'POST',body:{candidate_set_id:setId,candidate_ids:selected,weights},errors:{422:'Choose candidates and finite nonnegative scoring weights (maximum 100). Regenerate candidate sets after an engine upgrade.'}})
    setAnalysis(result);setDetailId('');setCompare(null)
    const history=await request(`/recommendations/analyses?candidate_set_id=${setId}&limit=100`);setRuns(history.filter(a=>a.candidate_set_id?.toLowerCase()===setId.toLowerCase()))
  }catch(e){setError(e.message)}finally{setBusy(false)}}
  async function open(id,comparison=false){setError('');try{const result=await request(`/recommendations/analyses/${id}`);if(comparison)setCompare(result);else{setAnalysis(result);setCompare(null);setDetailId('')}}catch(e){setError(e.message)}}
  async function openLegacy(id){setLegacyId(id);setSetId('');setCompare(null);if(id)await open(id)}
  async function convertLegacy(){setBusy(true);setError('');try{
    const result=await request(`/candidate-sets/from-analysis/${analysis.analysis_id}`,{method:'POST'})
    setWeights({read_weight:analysis.policy.read_weight,write_weight:analysis.policy.write_weight,storage_weight:analysis.policy.storage_weight})
    setSets(await request(`/candidate-sets${targetId?`?target_id=${targetId}`:''}`));setSetId(result.candidate_set_id);setLegacyId('')
  }catch(e){setError(e.message)}finally{setBusy(false)}}
  const rows=filterRecommendations(analysis?.recommendations || [],action,status,search)
  const detail=rows.find(r=>r.recommendation_id===detailId)||rows[0]
  return <div className="workflow-page">
    <section className="card"><div className="card-head"><div><h2>Score a saved candidate set</h2><p>Adjust tradeoffs and compare scoring runs over the same frozen evidence.</p></div><span className="badge">Step 4 · Prioritization</span></div><div className="card-body">
      <label className="field"><span>Candidate set to score</span><select aria-label="Candidate set to score" value={setId} disabled={busy} onChange={e=>setSetId(e.target.value)}><option value="">Select a candidate set</option>{sets.map(s=><option key={s.candidate_set_id} value={s.candidate_set_id}>{dateLabel(s.created_at_utc)} · {s.candidate_set_id.slice(0,8)} · collection {s.batch_id.slice(0,8)}</option>)}</select></label>
      {candidateSet&&<><p className="hint">Collection {candidateSet.batch_id} · Input hash {candidateSet.input_hash}</p><div className="actions"><button className="secondary" onClick={()=>onReview(setId)}>Review candidate shapes</button><button className="secondary" onClick={()=>onCollection(candidateSet.batch_id)}>View source collection</button></div>
        <h3>New scoring run</h3><div className="form-grid">{Object.entries(weights).map(([key,value])=><label className="field" key={key}><span>{key.replace('_weight','')} weight</span><input aria-label={`${key.replace('_weight','')} weight`} type="number" min="0" max="100" step="0.1" value={value} onChange={e=>setWeights({...weights,[key]:e.target.value===''?'':Number(e.target.value)})}/></label>)}</div>
        <details><summary>Candidates included in this run ({selected.length})</summary>{candidateSet.recommendations.map(r=><label className="check" key={r.recommendation_id}><input type="checkbox" checked={selected.includes(r.recommendation_id)} onChange={()=>setSelected(old=>old.includes(r.recommendation_id)?old.filter(id=>id!==r.recommendation_id):[...old,r.recommendation_id])}/>{r.action} · {r.schema_name}.{r.table_name} · {r.index_name}</label>)}</details><button disabled={busy||!selected.length||Object.values(weights).some(v=>v===''||!Number.isFinite(v)||v<0||v>100)} onClick={score}>{busy?'Scoring…':'Run scoring'}</button>
      </>}
    </div></section>
    {error&&<p className="notice error" role="alert">{error}</p>}
    {!!legacy.length&&<section className="card card-body"><label className="field"><span>Earlier analyses (before the workflow split)</span><select aria-label="Earlier analysis" value={legacyId} onChange={e=>openLegacy(e.target.value)}><option value="">Select an earlier analysis</option>{legacy.map(r=><option key={r.analysis_id} value={r.analysis_id}>{dateLabel(r.created_at_utc)} · collection {r.batch_id.slice(0,8)} · {r.analysis_id.slice(0,8)}</option>)}</select></label>{analysis&&!analysis.candidate_set_id&&<button disabled={busy} onClick={convertLegacy}>Create candidate set from saved evidence</button>}</section>}
    {!sets.length&&<div className="card empty"><h3>Generate a candidate set first</h3><p>Candidate Generator discovers the index shapes. Return here to choose weights and compare priorities.</p></div>}
    {!!runs.length&&<div className="form-grid"><label className="field"><span>Saved scoring run</span><select aria-label="Saved scoring run" value={analysis?.analysis_id||''} onChange={e=>open(e.target.value)}><option value="">Select a run</option>{runs.map(r=><option key={r.analysis_id} value={r.analysis_id}>{dateLabel(r.created_at_utc)} · {r.analysis_id.slice(0,8)}</option>)}</select></label><label className="field"><span>Compare with scoring run</span><select aria-label="Compare scoring run" value={compare?.analysis_id||''} onChange={e=>e.target.value?open(e.target.value,true):setCompare(null)}><option value="">No comparison</option>{runs.filter(r=>r.analysis_id!==analysis?.analysis_id).map(r=><option key={r.analysis_id} value={r.analysis_id}>{dateLabel(r.created_at_utc)} · {r.analysis_id.slice(0,8)}</option>)}</select></label></div>}
    {analysis&&<><p className="notice warning">Displayed run weights: read {analysis.policy.read_weight}, write {analysis.policy.write_weight}, storage {analysis.policy.storage_weight}. Net = read weight × base read benefit − write weight × base write penalty − storage weight × base maintenance. Scores are heuristic points. DROP remains advisory and requires review.</p>
      <div className="filter-bar card"><label>Action<select aria-label="Scoring action" value={action} onChange={e=>setAction(e.target.value)}><option value="">All actions</option>{['CREATE','RETAIN','DROP'].map(a=><option key={a}>{a}</option>)}</select></label><label>Status<select aria-label="Scoring status" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['Suggested','Review','Informational'].map(s=><option key={s}>{s}</option>)}</select></label><label>Search<input aria-label="Search scoring results" value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
      <section className="card table-scroll"><table><thead><tr><th>Rank</th><th>Action / object</th><th>Base read benefit</th><th>Base write penalty</th><th>Base maintenance</th><th>Net score</th>{compare&&<th>Change vs comparison</th>}<th/></tr></thead><tbody>{rows.map(r=>{
        const old=compare?.recommendations.find(x=>x.recommendation_id===r.recommendation_id)
        return <tr key={r.recommendation_id}><td>{r.rank}</td><td><strong>{r.action} · {r.schema_name}.{r.table_name}</strong><small>{r.status} · {r.index_name}</small></td>{['read_benefit','write_penalty','maintenance_penalty'].map(k=><td key={k}>{r.action==='CREATE'?scoreNumber(r.score_components[k]):'Rule-based'}</td>)}<td>{r.action==='CREATE'?scoreNumber(r.score):'Rule-based'}</td>{compare&&<td>{r.action==='CREATE'&&old?scoreNumber(r.score-old.score):'Not comparable'}</td>}<td><button className="text-button" onClick={()=>setDetailId(r.recommendation_id)}>Inspect {r.index_name}</button></td></tr>
      })}</tbody></table>{!rows.length&&<p className="card-body">No matching recommendations.</p>}</section>
      {detail&&<section className="card"><div className="card-head"><div><h2>{detail.action} · {detail.schema_name}.{detail.table_name}</h2><p>{detail.index_name}</p></div><span className="badge">{detail.protected?'Protected':detail.status}</span></div><div className="card-body"><p>{detail.rationale}</p><pre className="sql-preview">{detail.sql||'-- RETAIN: no structural change proposed.'}</pre>
        {detail.action==='CREATE'&&<p>Planning storage {number(detail.predicted_impact.storage_estimate_mb)} MB · Declared width {number(detail.score_components.row_width_bytes)} bytes · Base-table maintenance/hour {detail.score_components.writes_per_hour==null?'Unknown':scoreNumber(detail.score_components.writes_per_hour)} · Operational leaf writes/hour {detail.score_components.operational_leaf_writes_per_hour==null?'Unknown':scoreNumber(detail.score_components.operational_leaf_writes_per_hour)}. No calibrated duration prediction is available.</p>}
        {detail.usage_evidence&&<p>Usage observations: {JSON.stringify(detail.usage_evidence)}</p>}
        <h3>Related query evidence</h3>{detail.affected_queries.map(q=><details key={q.query_id}><summary>Query {q.query_id} · {number(q.execution_count)} executions</summary><p>{q.association} · Duration {number(q.total_duration_ms)} ms · CPU {number(q.total_cpu_ms)} ms · Reads {number(q.logical_reads)}</p><pre className="sql-preview">{q.query_sql_text}</pre></details>)}
        <h3>Provenance</h3><p className="hint">Analysis {analysis.analysis_id} · Candidate set {analysis.candidate_set_id || 'Earlier all-in-one analysis'} · Collection {analysis.batch_id} · Metadata {analysis.metadata_batch_id} · Engine {analysis.engine_version} · Input hash {analysis.input_hash}</p><pre className="evidence-json">{JSON.stringify(detail.source_evidence,null,2)}</pre><ul>{detail.warnings.map(w=><li key={w}>{w}</li>)}</ul>
      </div></section>}
    </>}
  </div>
}
