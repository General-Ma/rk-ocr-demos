import React, {useState, useRef, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const labels = {match:'Match', mismatch:'Mismatch', missing_in_ocr:'Missing OCR', no_ground_truth:'No ground truth', unresolved:'Unresolved'};
function DropZone({kind, title, file, onChange, disabled}) {
  const [error, setError] = useState('');
  function choose(files) {
    if (disabled) return;
    const chosen = files[0];
    const limit = kind === 'pdf' ? 20 : 1;
    if (files.length !== 1 || !chosen.name.toLowerCase().endsWith('.' + kind) || !chosen.size || chosen.size > limit * 1024 * 1024) {
      setError(`Choose one nonempty .${kind} file, up to ${limit} MB.`); return;
    }
    setError(''); onChange(chosen);
  }
  return <section className="drop" onDragOver={e => e.preventDefault()} onDrop={e => {e.preventDefault(); choose(e.dataTransfer.files);}}>
    <h2>{title}</h2><p>{kind === 'pdf' ? 'Scanned vital-sign forms (PDF, up to 20 MB / 12 pages)' : 'Scheduled readings in columns (UTF-8 CSV, up to 1 MB)'}</p>
    <label className="file-picker"><span>{file ? file.name : `Drop a ${kind.toUpperCase()} here, or choose a file`}</span><input aria-label={title} type="file" accept={'.' + kind} disabled={disabled} onChange={e => {if(e.target.files.length) choose(e.target.files); e.target.value='';}}/></label>
    {file && <div className="file-detail">{(file.size / 1024).toFixed(0)} KB <button disabled={disabled} onClick={() => {onChange(null); setError('');}}>Remove</button></div>}
    {error && <p role="alert" className="error">{error}</p>}
  </section>;
}
function App() {
  const [pdf, setPdf] = useState(null), [csv, setCsv] = useState(null);
  const [report, setReport] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [threshold, setThreshold] = useState(85), [filter, setFilter] = useState('all'), [selected, setSelected] = useState(null), [page, setPage] = useState(1), [zoom, setZoom] = useState(100);
  const sourceScroll = useRef(null);
  function revealSource() {
    const scroll = sourceScroll.current;
    if (scroll && selected?.page === page && selected.bbox) {
      scroll.scrollTop = selected.bbox[1] * (scroll.querySelector('img')?.clientHeight || 0) - scroll.clientHeight / 3;
    }
  }
  useEffect(revealSource, [selected, page, zoom]);
  function clear() {setReport(null); setPdf(null); setCsv(null); setSelected(null); setPage(1); setError(''); setFilter('all');}
  function changeFile(setter, value) {setter(value); setReport(null); setSelected(null); setError('');}
  async function run() {
    setBusy(true); setError(''); setReport(null); setSelected(null); setFilter('all');
    const data = new FormData(); data.append('pdf', pdf); data.append('csv', csv);
    try {
      const response = await fetch('/api/ocr', {method:'POST', body:data});
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The server could not process these files.');
      setReport(body); setPage(1); setZoom(100);
      if (body.rows.length) select(body.rows[0]);
    } catch (e) {setError(e instanceof SyntaxError ? 'The OCR server returned an invalid response. Check that FastAPI is running.' : e.message);}
    finally {setBusy(false);}
  }
  function select(row) {setSelected(row); if(row.page) setPage(row.page);}
  const low = row => row.confidence !== null && row.confidence * 100 < threshold;
  const rows = report?.rows || [];
  const count = status => rows.filter(r => r.status === status).length;
  const visible = rows.filter(r => filter === 'all' || (filter === 'review' ? r.status !== 'match' || low(r) : filter === 'low' ? low(r) : r.status === filter));
  const image = report?.pages[page - 1];
  const box = selected?.page === page ? selected.bbox : null;
  return <main>
    <header><div><h1>Chart review demo</h1><p>Compare a scanned vital-sign chart with scheduled readings.</p></div><button disabled={busy || (!pdf && !csv && !report)} onClick={clear}>Clear run</button></header>
    <div className="intake"><DropZone kind="pdf" title="Scanned document" file={pdf} disabled={busy} onChange={f => changeFile(setPdf, f)}/><DropZone kind="csv" title="Ground truth" file={csv} disabled={busy} onChange={f => changeFile(setCsv, f)}/></div>
    <div className="run-bar"><button className="primary" disabled={!pdf || !csv || busy} onClick={run}>{busy ? 'Processing…' : 'Run comparison'}</button><p>Files are sent to the FastAPI server for this run. Uploads and reports are not saved.</p></div>
    {busy && <p className="notice" role="status">Processing the scan and comparing readings. Local OCR may take several minutes; the first run may also download models.</p>}
    {error && <p className="error notice" role="alert">{error}</p>}
    {!report && !busy && <div className="empty"><h2>Review the reading and its source together</h2><p>After processing, select a result to highlight its location on the scanned page.</p><p>This demo supports the supplied vital-sign form layout. OCR output always needs human review.</p></div>}
    {report && <>
      <section className="report-head"><h2>Comparison report</h2><p className={report.aligned ? '' : 'warning'}>{report.alignment_note}</p><p>OCR suggestions are unverified. Confidence is an engine score, not a probability of correctness. Checkbox fields require manual review.</p>
        <div className="summary" aria-label="Report summary"><span><strong>{count('match') + count('mismatch')}</strong> compared</span><span><strong>{count('match')}</strong> matches</span><span><strong>{count('mismatch')}</strong> mismatches</span><span><strong>{rows.filter(low).length}</strong> low confidence</span><span><strong>{rows.length - count('match') - count('mismatch')}</strong> unscored / unresolved</span></div>
      </section>
      <div className="review">
        <section className="source"><div className="toolbar"><h2>Source document</h2><label>Page <select value={page} onChange={e => setPage(Number(e.target.value))}>{report.pages.map((_,i) => <option key={i} value={i+1}>{i+1} of {report.pages.length}</option>)}</select></label><label>Zoom <select value={zoom} onChange={e => setZoom(Number(e.target.value))}>{[75,100,150,200].map(v => <option key={v}>{v}</option>)}</select>%</label></div><div className="page-scroll" ref={sourceScroll}><div className="page-image" style={{width:zoom + '%'}}><img onLoad={revealSource} src={image?.image} alt={`Scanned chart, page ${page}`}/>{box && <div className="highlight" style={{left:box[0]*100+'%',top:box[1]*100+'%',width:(box[2]-box[0])*100+'%',height:(box[3]-box[1])*100+'%'}}/>}</div></div><p className="source-caption">{selected ? `Reading ${selected.reading} / ${selected.label} / ${selected.location_kind === 'detected' ? 'Detected text region' : 'Expected field / form region; inspect manually'}` : 'Select a result to inspect its source.'}</p></section>
        <section className="results"><div className="toolbar"><h2>Readings</h2><label>Show <select aria-label="Result filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All results</option><option value="review">Needs review</option><option value="low">Low confidence</option>{Object.entries(labels).map(([key,value]) => <option key={key} value={key}>{value}</option>)}</select></label><label>Low confidence below <input aria-label="Low confidence threshold" type="number" min="0" max="100" value={threshold} onChange={e => setThreshold(Math.min(100, Math.max(0, Number(e.target.value))))}/>%</label></div>
          <div className="table-scroll"><table><thead><tr><th>Reading / time</th><th>Field</th><th>OCR / CSV</th><th>Result / confidence</th></tr></thead><tbody>{visible.map(row => <tr key={row.id} className={selected?.id === row.id ? 'selected' : ''}><td><button className="row-link" onClick={() => select(row)} aria-pressed={selected?.id === row.id}>#{row.reading} / {row.scheduled_time || 'No slot'}</button><small>Actual {row.actual_time || (row.actual_time_text ? `${row.actual_time_text} (unverified)` : 'unreadable')}<br/>Page {row.page || '—'}</small></td><td>{row.label}</td><td><span className="value">{row.ocr_text || '—'}</span>{row.ocr_value !== row.ocr_text && <small>Parsed: {row.ocr_value}</small>}<small>CSV: {row.csv_text || '(blank)'}</small></td><td><span className={'status ' + row.status}>{labels[row.status]}</span><small className={low(row) ? 'warning' : ''}>{row.confidence === null ? 'No confidence score' : `${Math.round(row.confidence * 100)}%${low(row) ? ' / Low confidence' : ''}`}</small></td></tr>)}</tbody></table>{!visible.length && <p className="no-results">No results in this filter.</p>}</div><p className="source-caption">{visible.length} of {rows.length} values / select a reading time to view its source</p>
        </section>
      </div>
    </>}
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
