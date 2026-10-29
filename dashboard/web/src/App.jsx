import React, { useEffect, useRef, useState } from 'react'
import TargetForm from './components/TargetForm.jsx'
import { request, dateLabel, number } from './api/client.js'
import './styles.css'

const navigation = [
  ['overview','Overview','M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z'],
  ['targets','Database targets','M4 6c0-4 16-4 16 0s-16 4-16 0z M4 6v12c0 4 16 4 16 0V6 M4 12c0 4 16 4 16 0'],
  ['collector','Workload collector','M4 12h4l3-8 3 16 3-8h3'],
  ['history','Workload history','M3 12a9 9 0 1 0 3-7 M3 3v6h6 M12 7v5l4 2'],
  ['candidates','Candidate generator','M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h4'],
  ['scoring','Scoring engine','M4 20V10 M10 20V4 M16 20v-8 M22 20V7'],
  ['forecasts','ML forecaster','M3 17l6-6 4 3 8-10 M16 4h5v5'],
  ['safety','Safety controller','M12 3l8 4v6c0 5-8 9-8 9S4 18 4 13V7z M8 12l3 3 5-6'],
  ['reports','Reporting','M5 3h10l4 4v14H5z M9 11h6 M9 15h6'],
  ['platform','Platform / CI-CD','M7 8l-4 4 4 4 M17 8l4 4-4 4 M14 4l-4 16'],
]
const labels = Object.fromEntries(navigation.map(([id,label])=>[id,label]))
const componentLabels = { SOURCE_STATE:'Source state', QUERY_RUNTIME:'Query Store runtime', INDEX_USAGE:'Index usage', INDEX_OPERATIONAL:'Operational statistics', MISSING_INDEX:'Missing-index evidence', METADATA:'Schema metadata' }
const terminal = ['Completed','Partial','Failed','Cancelled']
const placeholderContent = {
  candidates: ['Turn workload evidence into physical-design candidates.', ['Index creation candidates','Existing-index overlap inspection','Retain and drop analysis','Partitioning opportunities']],
  scoring: ['Rank candidates by expected benefit and maintenance cost.', ['Read-benefit estimates','Write and storage penalties','Score breakdowns','Evidence-linked explanations']],
  forecasts: ['Forecast workload changes from collected history.', ['Time-bucketed features','Baseline and ML comparisons','Hot query and table forecasts','Proactive tuning signals']],
  safety: ['Approve, validate, and reverse tuning changes.', ['Protected-index rules','Approval and execution workflow','Regression thresholds','Rollback and action audit']],
  reports: ['Compare predicted and observed tuning outcomes.', ['Before and after comparisons','Experiment report exports','Prediction accuracy','Decision and action history']],
  platform: ['Manage application operations and release quality.', ['Repository readiness','Build and test pipelines','Deployment configuration','Collector scheduling']],
}
function Icon({path}) { return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={path}/></svg> }
function Badge({status}) { return <span className={`badge ${String(status).toLowerCase()}`}>{status || 'Not started'}</span> }
function Empty({title,children}) { return <div className="empty"><div className="empty-symbol">◇</div><h3>{title}</h3><p>{children}</p></div> }
function Metric({label,value,unit,note}) { return <div className="metric"><span>{label}</span><strong>{value}<small>{unit}</small></strong>{note && <p>{note}</p>}</div> }
function HistoryTable({rows,targets,onOpen}) { return <div className="table-scroll"><table><thead><tr><th>Collection</th><th>Target</th><th>Created</th><th>Status</th><th>Completeness</th><th/></tr></thead><tbody>{rows.map(row=><tr key={row.batch_id}><td><strong>{row.label || 'Unlabelled collection'}</strong><small>{row.window_source || 'Window pending'}</small></td><td>{targets.find(t=>t.target_id===row.target_id)?.name || 'Unknown target'}</td><td>{dateLabel(row.created_at_utc)}</td><td><Badge status={row.status}/></td><td><div className="progress"><span style={{width:`${row.completeness_percent}%`}}/></div><small>{number(row.completeness_percent)}%</small></td><td><button className="text-button" onClick={()=>onOpen(row.batch_id)}>View →</button></td></tr>)}</tbody></table></div> }

export default function App() {
  const [page,setPage] = useState('overview')
  const [targets,setTargets] = useState([])
  const [history,setHistory] = useState([])
  const [targetId,setTargetId] = useState('')
  const [filters,setFilters] = useState({status:'',from:'',to:''})
  const [adding,setAdding] = useState(false)
  const [batchId,setBatchId] = useState('')
  const [summary,setSummary] = useState(null)
  const [components,setComponents] = useState([])
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [notice,setNotice] = useState('')
  const [running,setRunning] = useState(false)
  const [refreshKey,setRefreshKey] = useState(0)
  const [collection,setCollection] = useState({label:'',mode:'automatic',start:'',end:'',force_metadata:false})
  const [checking,setChecking] = useState('')
  const runInFlight=useRef(false)
  const selected=targets.find(t=>t.target_id===targetId)
  const refresh=()=>setRefreshKey(k=>k+1)
  function navigate(id) { setPage(id); setError(''); setNotice('') }
  useEffect(()=>{
    const controller=new AbortController()
    setLoading(true);setError('')
    const params=new URLSearchParams({limit:'100'})
    if(targetId)params.set('target_id',targetId)
    if(page==='history' && filters.status)params.set('status',filters.status)
    if(page==='history' && filters.from)params.set('created_from_utc',new Date(`${filters.from}T00:00:00`).toISOString())
    if(page==='history' && filters.to)params.set('created_to_utc',new Date(`${filters.to}T23:59:59.999`).toISOString())
    Promise.all([request('/targets?limit=500',{signal:controller.signal}), request(`/collections?${params}`,{signal:controller.signal})])
      .then(([ts,bs])=>{setTargets(ts);setHistory(bs)})
      .catch(e=>{if(e.name!=='AbortError'){setError(e.message);setHistory([])}})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return ()=>controller.abort()
  },[page,targetId,filters.status,filters.from,filters.to,refreshKey])
  useEffect(()=>{
    if(!batchId){setSummary(null);setComponents([]);return}
    const controller=new AbortController();let timer
    setSummary(null);setComponents([])
    async function poll(){
      try {
        const [s,c]=await Promise.all([request(`/collections/${batchId}/summary`,{signal:controller.signal}),request(`/collections/${batchId}/components`,{signal:controller.signal})])
        if(controller.signal.aborted)return
        setSummary(s);setComponents(c)
        if(!terminal.includes(s.batch.status))timer=setTimeout(poll,2000)
      } catch(e){if(e.name!=='AbortError')setError(e.message)}
    }
    poll();return ()=>{controller.abort();clearTimeout(timer)}
  },[batchId,refreshKey])
  async function collect(existingId){
    if(runInFlight.current)return
    if(!existingId && !selected){setError('Select a saved database target first.');return}
    if(!existingId && collection.mode==='explicit' && (!collection.start || !collection.end || collection.start>collection.end)){setError('Choose a valid start and end for the collection window.');return}
    runInFlight.current=true;setRunning(true);setError('');setNotice('')
    try{
      let id=existingId
      if(!id){
        const body={target_id:targetId,label:collection.label || null,force_metadata:collection.force_metadata,
          requested_window_start_utc:collection.mode==='explicit'?new Date(collection.start).toISOString():null,
          requested_window_end_utc:collection.mode==='explicit'?new Date(collection.end).toISOString():null}
        const batch=await request('/collections',{method:'POST',body});id=batch.batch_id
      }
      setBatchId(id)
      const result=await request(`/collections/${id}/collect`,{method:'POST'})
      setNotice(`Collection ${result.final_status.toLowerCase()}. ${result.completed_components} components completed, ${result.skipped_components} skipped, ${result.failed_components} failed.`)
    }catch(e){setError(e.message)}finally{runInFlight.current=false;setRunning(false);refresh()}
  }
  async function cancel(){
    if(!summary || !window.confirm('Cancel this inactive collection? Active collectors cannot be cancelled here. You can create a new batch afterward.'))return
    try{await request(`/collections/${batchId}/cancel`,{method:'POST'});setNotice('Inactive collection cancelled. Create a new batch to retry.');refresh()}catch(e){setError(e.message)}
  }
  async function checkTarget(id){
    setChecking(id);setError('');setNotice('')
    try{const result=await request(`/targets/${id}/test-connection`,{method:'POST'});setNotice(result.collector_ready?'Collector access validated.':result.connected?'Connected, but collector permissions need attention.':'Connection failed. Review the target configuration and server credential reference.')}catch(e){setError(e.message)}finally{setChecking('')}
  }
  function openBatch(id){setBatchId(id);navigate('collector')}
  const latest=history[0]
  const detail=summary?.batch
  const overview=<>
    <div className="hero"><div><p className="eyebrow">OBSERVE · UNDERSTAND · OPTIMIZE</p><h2>Your workload is the starting point.</h2><p>Collect SQL Server evidence, preserve its history, and prepare for informed tuning decisions.</p><button onClick={()=>navigate('collector')}>Collect workload <span>→</span></button></div><div className="hero-art" aria-hidden="true"><div className="database-stack"><i/><i/><i/></div><div className="signal-line"/><span>SQL SERVER</span><span>WORKLOAD EVIDENCE</span></div></div>
    <div className="metrics"><Metric label="Saved targets" value={targets.length}/><Metric label="Recent collections" value={history.length} note="Up to 100 matching batches"/><Metric label="Completed collections" value={history.filter(b=>b.status==='Completed').length} note="Within the loaded history"/><Metric label="Latest completeness" value={latest?number(latest.completeness_percent):'—'} unit={latest?'%':''} note={latest?dateLabel(latest.created_at_utc):'Run your first collection'}/></div>
    <div className="section-title"><h2>Collection activity</h2><button className="text-button" onClick={()=>navigate('history')}>View history →</button></div>
    <div className="card">{loading?<p className="loading">Loading collection history…</p>:history.length?<HistoryTable rows={history.slice(0,5)} targets={targets} onOpen={openBatch}/>:<Empty title="No collections yet">Save a database target, then collect your first workload window.</Empty>}</div>
    <div className="section-title"><h2>Tuning pipeline</h2><span className="hint">Built around collected evidence</span></div><div className="pipeline">{[['collector','01','Collect evidence','Available'],['candidates','02','Generate candidates','Planned'],['scoring','03','Score & forecast','Planned'],['safety','04','Validate changes','Planned']].map(([id,n,title,status])=><button className="pipeline-step" key={n} onClick={()=>navigate(id)}><span>{n}</span><h3>{title}</h3><Badge status={status}/></button>)}</div>
  </>
  const targetPage=<><div className="section-title"><p>Saved metadata and credential references. Passwords stay on the server.</p><button onClick={()=>setAdding(true)}>+ Add target</button></div>{adding && <TargetForm close={()=>setAdding(false)} onSaved={target=>{setAdding(false);setTargetId(target.target_id);setNotice('Target saved and selected.');refresh()}}/>}<div className="target-grid">{targets.map(t=><article className="card target-card" key={t.target_id}><div className="target-icon"><Icon path={navigation[1][2]}/></div><Badge status={t.is_enabled?'Enabled':'Disabled'}/><h2>{t.name}</h2><p>{t.server}</p><strong className="database-name">{t.database}</strong><dl><dt>Authentication</dt><dd>{t.authentication==='windows'?'Windows':'SQL Server'}</dd><dt>Query timeout</dt><dd>{t.query_timeout_seconds}s</dd><dt>Credential reference</dt><dd>{t.credential_reference || 'Not required'}</dd></dl><div className="actions"><button className="secondary" disabled={checking===t.target_id} onClick={()=>checkTarget(t.target_id)}>{checking===t.target_id?'Testing…':'Test access'}</button><button className="text-button" disabled={!t.is_enabled} onClick={()=>{setTargetId(t.target_id);navigate('collector')}}>Collect →</button></div></article>)}</div>{!targets.length&&!loading&&!adding&&<div className="card"><Empty title="Add your first SQL Server target">Validate connectivity and collector permissions before saving.</Empty></div>}</>
  const historyPage=<><div className="filter-bar card"><label>Status<select value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}><option value="">All statuses</option>{['Pending','Collecting',...terminal].map(s=><option key={s}>{s}</option>)}</select></label><label>Created from<input type="date" value={filters.from} onChange={e=>setFilters({...filters,from:e.target.value})}/></label><label>Created through<input type="date" value={filters.to} onChange={e=>setFilters({...filters,to:e.target.value})}/></label><button className="secondary" onClick={()=>{setFilters({status:'',from:'',to:''});setTargetId('')}}>Clear filters</button></div><p className="hint">Dates use your local timezone and filter batch creation time. Showing up to 100 matching collections. Overlapping batches share Query Store evidence; their totals must not be added together.</p><div className="card">{loading?<p className="loading">Loading history…</p>:history.length?<HistoryTable rows={history} targets={targets} onOpen={openBatch}/>:<Empty title="No matching collections">Try another target, status, or date range.</Empty>}</div></>
  const collectorPage=<><div className="collector-layout"><section className="card"><div className="card-head"><div><h2>New collection</h2><p>Read telemetry and save it to the repository.</p></div><span className="dot-label">Read-only target access</span></div><div className="card-body"><label className="field"><span>Database target</span><select value={targetId} onChange={e=>setTargetId(e.target.value)} disabled={running}><option value="">Select a saved target</option>{targets.filter(t=>t.is_enabled).map(t=><option key={t.target_id} value={t.target_id}>{t.name} · {t.database}</option>)}</select></label><label className="field"><span>Collection label</span><input maxLength={200} value={collection.label} onChange={e=>setCollection({...collection,label:e.target.value})} placeholder="e.g. Afternoon workload" disabled={running}/></label><label className="field"><span>Workload window</span><select value={collection.mode} onChange={e=>setCollection({...collection,mode:e.target.value})} disabled={running}><option value="automatic">Automatic incremental window</option><option value="explicit">Explicit historical window</option></select></label>{collection.mode==='explicit'&&<div className="form-grid"><label className="field"><span>Start (local time)</span><input type="datetime-local" value={collection.start} onChange={e=>setCollection({...collection,start:e.target.value})} disabled={running}/></label><label className="field"><span>End (local time)</span><input type="datetime-local" value={collection.end} onChange={e=>setCollection({...collection,end:e.target.value})} disabled={running}/></label></div>}<label className="check"><input type="checkbox" checked={collection.force_metadata} onChange={e=>setCollection({...collection,force_metadata:e.target.checked})} disabled={running}/> Force metadata refresh</label><p className="hint">Automatic collection continues from the last Query Store watermark. Metadata is refreshed when due. Zero rows can be valid while Query Store intervals are still open.</p><button disabled={running||!selected} onClick={()=>collect()}>{running?'Collecting workload…':'Start collection →'}</button></div></section><section className="card collector-guide"><p className="eyebrow">WHAT WE CAPTURE</p><h2>Evidence, with provenance.</h2>{Object.values(componentLabels).map((name,i)=><div className="source-line" key={name}><span>0{i+1}</span>{name}</div>)}<p className="hint">Individual source failures remain visible. Intentional metadata skips count as healthy completion.</p></section></div>
    {batchId&&<section className="card batch-detail"><div className="card-head"><div><h2>{detail?.label || 'Collection details'}</h2><p className="mono">{batchId}</p></div>{detail&&<Badge status={detail.status}/>}</div>{!summary?<p className="loading">Loading collection details…</p>:<div className="card-body"><div className="metrics compact"><Metric label="Executions" value={number(summary.query_runtime.execution_count)}/><Metric label="Total duration" value={number(summary.query_runtime.total_duration_ms)} unit=" ms"/><Metric label="CPU time" value={number(summary.query_runtime.total_cpu_ms)} unit=" ms"/><Metric label="Logical reads" value={number(summary.query_runtime.logical_reads)}/></div><div className="detail-grid"><div><h3>Workload window</h3><p>{detail.window_source || 'Not resolved'} · {number(detail.completeness_percent)}% complete</p><small>Effective: {dateLabel(detail.effective_window_start_utc)} → {dateLabel(detail.effective_window_end_utc)}</small><small>Requested: {dateLabel(detail.requested_window_start_utc)} → {dateLabel(detail.requested_window_end_utc)}</small></div><div><h3>Source & continuity</h3><p>Query Store: {summary.source_state?.query_store_actual_state || 'Not observed'}</p><small>DMV reset: {summary.source_state ? String(summary.source_state.dmv_reset_detected) : 'Unknown'} · Query Store reset: {summary.source_state ? String(summary.source_state.query_store_reset_detected) : 'Unknown'}</small><small>Current watermark: {dateLabel(summary.target_query_watermark_utc)}</small></div></div><h3 className="section-title">Component results</h3><div className="table-scroll"><table><thead><tr><th>Source</th><th>Status</th><th>Rows</th><th>Details</th></tr></thead><tbody>{components.map(c=><tr key={c.component_name}><td>{componentLabels[c.component_name]||c.component_name}</td><td><Badge status={c.status}/></td><td>{c.rows_collected ?? '—'}</td><td>{c.status_message || c.error_message || (c.completed_at_utc?`Finished ${dateLabel(c.completed_at_utc)}`:'—')}</td></tr>)}</tbody></table></div><p className="hint">Query totals are derived from Query Store averages and execution counts for this batch. Times are shown in your local timezone. Metadata rows belong to this batch; the current reusable metadata source is <span className="mono">{summary.metadata_source_batch_id||'not available'}</span>.</p>{detail.failure_reason&&<p className="notice warning">{detail.failure_reason}</p>}{detail.status==='Pending'&&<button disabled={running} onClick={()=>collect(batchId)}>Run this pending collection</button>}{['Pending','Collecting'].includes(detail.status)&&!running&&<button className="secondary" onClick={cancel}>Cancel inactive batch</button>}</div>}</section>}
  </>
  const placeholder=placeholderContent[page]
  return <div className="app-shell"><aside className="sidebar"><a href="#" className="brand" onClick={e=>{e.preventDefault();navigate('overview')}}><span className="brand-symbol">≋</span><span>Database Tuner<small>WORKLOAD INTELLIGENCE</small></span></a><p className="nav-caption">WORKSPACE</p><nav>{navigation.slice(0,4).map(([id,label,path])=><button key={id} aria-current={page===id?'page':undefined} className={page===id?'active':''} onClick={()=>navigate(id)}><Icon path={path}/>{label}</button>)}<p className="nav-caption">TUNING & OPERATIONS</p>{navigation.slice(4).map(([id,label,path])=><button key={id} aria-current={page===id?'page':undefined} className={page===id?'active':''} onClick={()=>navigate(id)}><Icon path={path}/>{label}<span className="nav-dot"/></button>)}</nav><div className="sidebar-bottom"><span className="status-dot"/> Local development<small>SQL Server · Capstone</small></div></aside><div className="main-shell"><header className="topbar"><span>Workspace <b>/</b> {labels[page]}</span><div><span className="version">Sprint 1</span><span className="avatar">DT</span></div></header><main><div className="page-header"><div><p className="eyebrow">AUTOMATED DATABASE TUNER</p><h1>{labels[page]}</h1><p>{page==='overview'?'A clear view of your databases, workload evidence, and tuning pipeline.':page==='targets'?'Manage the databases your collector observes.':page==='collector'?'Capture workload telemetry without changing target data.':page==='history'?'Explore persisted collection windows and outcomes.':placeholder?.[0]}</p></div><div className="page-controls"><select aria-label="Filter by target" value={targetId} onChange={e=>setTargetId(e.target.value)}><option value="">All targets</option>{targets.map(t=><option value={t.target_id} key={t.target_id}>{t.name}</option>)}</select><button className="secondary" onClick={refresh}>↻ Refresh</button></div></div>
      {error&&<div className="notice error" role="alert">{error}</div>}{notice&&<div className={`notice ${/failed/i.test(notice)?"error":/(attention|partial)/i.test(notice)?"warning":"success"}`} role="status">{notice}</div>}
      {page==='overview'?overview:page==='targets'?targetPage:page==='history'?historyPage:page==='collector'?collectorPage:<><section className="card planned-hero"><Badge status="Planned"/><h2>{labels[page]}</h2><p>{placeholder?.[0]}</p><p>This workspace is ready for the next implementation phase. Backend integration is not available yet.</p><button className="secondary" onClick={()=>navigate('history')}>Explore collected evidence →</button></section><div className="planned-grid">{placeholder?.[1].map((item,i)=><article className="card planned-card" key={item}><span>0{i+1}</span><h3>{item}</h3><p>Planned functionality</p></article>)}</div></>}
      <footer><span>AutoTunerRepository · Persistent workload history</span><span>Collector available · Tuning modules planned</span></footer></main></div></div>
}
