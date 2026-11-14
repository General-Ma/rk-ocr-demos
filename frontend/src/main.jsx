import React, {useState, useRef, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const labels = {match:'Match', mismatch:'Mismatch', missing_in_ocr:'Missing OCR', no_ground_truth:'No source value', unresolved:'Unresolved'};
const fields = {performed:'Vital status performed', systolic:'Systolic blood pressure', diastolic:'Diastolic blood pressure', heart_rate:'Heart rate', temperature:'Temperature', weight:'Weight', significant:'Clinically significant'};

function FilePicker({kind, files, onChange, disabled, multiple = false}) {
  const [error, setError] = useState('');
  function choose(incoming) {
    if (disabled) return;
    const added = Array.from(incoming);
    const next = multiple ? [...files, ...added] : added;
    const limit = kind === 'pdf' ? 20 : 1;
    if (!added.length || next.length > (multiple ? 10 : 1) || next.some(f => !f.name.toLowerCase().endsWith('.' + kind) || !f.size) || next.reduce((sum, f) => sum + f.size, 0) > limit * 1024 * 1024) {
      setError(`Choose ${multiple ? 'up to 10 nonempty PDFs' : 'one nonempty source file (.csv)'}, at most ${limit} MB in total.`);
      return;
    }
    setError(''); onChange(next);
  }
  return <div className="file-area" onDragOver={e => e.preventDefault()} onDrop={e => {e.preventDefault(); choose(e.dataTransfer.files);}}>
    <label className="file-picker"><span>{multiple ? 'Drop PDFs here, or choose documents' : 'Drop a source file here, or choose a file'}</span>
      <input aria-label={multiple ? 'Upload documents' : 'Upload source'} type="file" multiple={multiple} accept={'.' + kind} disabled={disabled} onChange={e => {if (e.target.files.length) choose(e.target.files); e.target.value = '';}}/>
    </label>
    {files.length > 0 && <ol className="file-list">{files.map((file, i) => <li key={`${file.name}-${i}`}><span>{file.name} <small>{Math.ceil(file.size / 1024)} KB</small></span><button aria-label={`Remove ${file.name}`} disabled={disabled} onClick={() => {onChange(files.filter((_, index) => index !== i)); setError('');}}>Remove</button></li>)}</ol>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function SourceConfig({source, setSource, csv, setCsv, disabled}) {
  return <>
    <label className="source-type">Source type <select value={source} disabled={disabled} onChange={e => setSource(e.target.value)}><option value="csv">Upload file</option><option value="database">Database</option><option value="api">API</option></select></label>
    {source === 'csv' ? <><p>Scheduled readings in columns, fields in rows. UTF-8 .csv format, up to 1 MB.</p><FilePicker kind="csv" files={csv ? [csv] : []} onChange={files => setCsv(files[0] || null)} disabled={disabled}/></> : <>
      <p className="notice">Configuration preview only. {source === 'database' ? 'Database' : 'API'} connections are not enabled in this demo. Select Upload file to continue.</p>
      {source === 'database' ? <div className="config-grid" key="database">
        <label>Database engine<select defaultValue="PostgreSQL"><option>PostgreSQL</option><option>MySQL</option><option>SQL Server</option></select></label>
        <label>Host<input placeholder="localhost" autoComplete="off"/></label>
        <label>Port<input type="number" placeholder="5432" min="1" max="65535"/></label>
        <label>Database name<input placeholder="Study database" autoComplete="off"/></label>
        <label>Username<input autoComplete="off" placeholder="Username"/></label>
        <label>Password<input type="password" autoComplete="new-password" placeholder="Preview only; do not enter real credentials"/></label>
        <label className="wide">Table or view<input placeholder="vital_sign_readings" autoComplete="off"/></label>
      </div> : <div className="config-grid" key="api">
        <label className="wide">Endpoint URL<input type="url" placeholder="https://example.com/readings" autoComplete="off"/></label>
        <label>Method<select defaultValue="GET"><option>GET</option><option>POST</option></select></label>
        <label>Authentication<select defaultValue="none"><option value="none">None</option><option value="bearer">Bearer token</option><option value="key">API key</option></select></label>
        <label className="wide">Token or API key<input type="password" autoComplete="new-password" placeholder="Preview only; do not enter real credentials"/></label>
        <label className="wide">Response data path<input placeholder="data.readings" autoComplete="off"/></label>
      </div>}
      <button disabled>Test connection (not available in demo)</button>
    </>}
  </>;
}

function extractedRows(extraction) {
  let id = 0, readingNumber = 0;
  return extraction.documents.flatMap(doc => doc.readings.flatMap(reading => {
    readingNumber++;
    return Object.entries(fields).map(([field, label]) => {
      const item = reading.fields[field] || {};
      return {id:id++, reading:readingNumber, field, label, document_name:doc.name, page:reading.page, local_page:reading.local_page,
        actual_time:reading.time, actual_time_text:reading.time_text, ocr_text:item.text || '', ocr_value:item.value ?? item.text ?? '',
        confidence:item.confidence ?? null, bbox:item.bbox || reading.bbox, location_kind:item.location_kind || 'form',
        status:item.uncertain ? 'unresolved' : !item.text ? 'missing_in_ocr' : null};
    });
  }));
}

function Review({extraction, report = null}) {
  const rows = report ? report.rows : extractedRows(extraction);
  const [threshold, setThreshold] = useState(85), [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(rows[0] || null), [page, setPage] = useState(rows[0]?.page || 1), [zoom, setZoom] = useState(100);
  const sourceScroll = useRef(null);
  function revealSource() {
    const scroll = sourceScroll.current;
    if (scroll && selected?.page === page && selected.bbox) scroll.scrollTop = selected.bbox[1] * (scroll.querySelector('img')?.clientHeight || 0) - scroll.clientHeight / 3;
  }
  useEffect(revealSource, [selected, page, zoom]);
  function select(row) {setSelected(row); if(row.page) setPage(row.page);}
  const low = row => row.confidence != null && row.confidence * 100 < threshold;
  const count = status => rows.filter(r => r.status === status).length;
  const visible = rows.filter(r => filter === 'all' || (filter === 'review' ? (report ? r.status !== 'match' : !!r.status) || low(r) : filter === 'low' ? low(r) : r.status === filter));
  const image = extraction.pages[page - 1];
  const box = selected?.page === page ? selected.bbox : null;
  return <>
    {report && <><p className={report.aligned ? '' : 'warning'}>{report.alignment_note}</p>
      {report.documents?.length > 1 && <ul>{report.documents.map((doc, i) => <li key={i} className={doc.aligned ? '' : 'warning'}>{doc.name}: {doc.note}</li>)}</ul>}
      <div className="summary" aria-label="Report summary"><span><strong>{count('match') + count('mismatch')}</strong> compared</span><span><strong>{count('match')}</strong> matches</span><span><strong>{count('mismatch')}</strong> mismatches</span><span><strong>{rows.filter(low).length}</strong> low confidence</span><span><strong>{rows.length - count('match') - count('mismatch')}</strong> unscored / unresolved</span></div>
    </>}
    <p className="review-note">OCR suggestions are unverified. Confidence is an engine score, not a probability of correctness. Checkbox fields require manual review.</p>
    <div className="review">
      <section className="source"><div className="toolbar"><h3>Uploaded document</h3><label>Page <select aria-label="Uploaded page" value={page} onChange={e => setPage(Number(e.target.value))}>{extraction.pages.map(p => <option key={p.page} value={p.page}>{p.document_name} / page {p.local_page}</option>)}</select></label><label>Zoom <select value={zoom} onChange={e => setZoom(Number(e.target.value))}>{[75,100,150,200].map(v => <option key={v}>{v}</option>)}</select>%</label></div>
        <div className="page-scroll" ref={sourceScroll}><div className="page-image" style={{width:zoom + '%'}}><img onLoad={revealSource} src={image?.image} alt={`${image?.document_name}, page ${image?.local_page}`}/>{box && <div className="highlight" style={{left:box[0]*100+'%',top:box[1]*100+'%',width:(box[2]-box[0])*100+'%',height:(box[3]-box[1])*100+'%'}}/>}</div></div>
        <p className="source-caption">{selected ? `${selected.label} / ${selected.location_kind === 'detected' ? 'Detected text region' : 'Expected field or form region; inspect manually'}` : 'Select a result to inspect the uploaded document.'}</p>
      </section>
      <section className="results"><div className="toolbar"><h3>{report ? 'Audit results' : 'Extracted values'}</h3><label>Show <select aria-label="Result filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All results</option><option value="review">Needs review</option><option value="low">Low confidence</option>{Object.entries(labels).filter(([key]) => report || ['missing_in_ocr','unresolved'].includes(key)).map(([key,value]) => <option key={key} value={key}>{value}</option>)}</select></label><label>Low confidence below <input aria-label="Low confidence threshold" type="number" min="0" max="100" value={threshold} onChange={e => setThreshold(Math.min(100, Math.max(0, Number(e.target.value))))}/>%</label></div>
        <div className="table-scroll"><table><thead><tr><th>Document / reading</th><th>Field</th><th>Uploaded</th>{report && <th>Source</th>}<th>{report ? 'Result / confidence' : 'Review / confidence'}</th></tr></thead><tbody>{visible.map(row => <tr key={row.id} className={selected?.id === row.id ? 'selected' : ''}>
          <td><button className="row-link" onClick={() => select(row)} aria-pressed={selected?.id === row.id}>#{row.reading}{report ? ` / ${row.scheduled_time || 'No slot'}` : ''}</button><small>{row.document_name || 'No uploaded document'}<br/>Actual {row.actual_time || (row.actual_time_text ? `${row.actual_time_text} (unverified)` : 'unreadable')}<br/>Page {row.local_page || '—'}</small></td>
          <td>{row.label}</td><td><span className="value">{row.ocr_value || row.ocr_text || '—'}</span>{row.ocr_value && row.ocr_value !== row.ocr_text && <small>Original: {row.ocr_text}</small>}</td>{report && <td><span className="value">{row.csv_text || '(blank)'}</span></td>}
          <td><span className={'status ' + (row.status || '')}>{row.status ? labels[row.status] : 'Not audited'}</span><small className={low(row) ? 'warning' : ''}>{row.confidence == null ? 'No confidence score' : `${Math.round(row.confidence * 100)}%${low(row) ? ' / Low confidence' : ''}`}</small></td>
        </tr>)}</tbody></table>{!visible.length && <p className="no-results">No results in this filter.</p>}</div><p className="source-caption">{visible.length} of {rows.length} values / select a reading to view the uploaded document</p>
      </section>
    </div>
  </>;
}

async function post(path, data) {
  const response = await fetch(path, {method:'POST', body:data});
  let body;
  try {body = await response.json();} catch {throw new Error('The server returned an invalid response. Check that FastAPI is running.');}
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The server could not process this request.');
  return body;
}

function App() {
  const [panel, setPanel] = useState('source');
  const [source, setSource] = useState('csv'), [csv, setCsv] = useState(null), [pdfs, setPdfs] = useState([]);
  const [confirmed, setConfirmed] = useState(null);
  const [extraction, setExtraction] = useState(null), [report, setReport] = useState(null);
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [showExtraction, setShowExtraction] = useState(true);
  const [runKey, setRunKey] = useState(0);
  const heading = useRef(null);
  useEffect(() => {heading.current?.focus();}, [panel]);
  function clear() {setPanel('source'); setConfirmed(null); setSource('csv'); setCsv(null); setPdfs([]); setExtraction(null); setReport(null); setError(''); setShowExtraction(true); setRunKey(k => k + 1);}
  function changeSource(value) {setSource(value); setConfirmed(null); setReport(null); setError(''); setShowExtraction(true);}
  function changeCsv(value) {setCsv(value); setConfirmed(null); setReport(null); setError(''); setShowExtraction(true);}
  function changePdfs(value) {setPdfs(value); setExtraction(null); setReport(null); setError(''); setShowExtraction(true);}
  async function confirmSource() {
    setBusy('source'); setError(''); setConfirmed(null);
    const data = new FormData(); data.append('source', csv);
    try {setConfirmed(await post('/api/source', data)); setPanel('documents');} catch (e) {setError(e.message);} finally {setBusy('');}
  }
  async function processDocuments() {
    setBusy('extract'); setError(''); setExtraction(null); setReport(null); setShowExtraction(true);
    const data = new FormData(); pdfs.forEach(pdf => data.append('pdfs', pdf));
    try {setExtraction(await post('/api/extract', data));} catch (e) {setError(e.message);} finally {setBusy('');}
  }
  async function audit() {
    setBusy('audit'); setError(''); setReport(null);
    const data = new FormData(); data.append('csv', csv); data.append('extraction', JSON.stringify({documents:extraction.documents}));
    try {setReport(await post('/api/compare', data)); setShowExtraction(false);} catch (e) {setError(e.message);} finally {setBusy('');}
  }
  function editSource() {setError(''); setPanel('source');}
  return <main>
    <header><div><h1>Renkind Audit</h1><p>Review uploaded documents against your source data.</p></div><button disabled={!!busy} onClick={clear}>Clear run</button></header>
    <nav className="wizard-nav" aria-label="Review workflow"><span aria-current={panel === 'source' ? 'step' : undefined}>Source data</span><span aria-hidden="true">/</span><span aria-current={panel === 'documents' ? 'step' : undefined}>Documents and audit</span></nav>
    {panel === 'source' ? <section className="wizard-panel" aria-labelledby="source-heading">
      <h2 id="source-heading" ref={heading} tabIndex={-1}>Configure source data</h2><p>Choose the reference data for your document audit.</p>
      <fieldset disabled={!!busy} className="source-config" key={runKey}><SourceConfig source={source} setSource={changeSource} csv={csv} setCsv={changeCsv} disabled={!!busy}/></fieldset>
      <div className="run-bar"><button className="primary" disabled={source !== 'csv' || !csv || !!busy} onClick={confirmSource}>{busy === 'source' ? 'Confirming source…' : 'Confirm source'}</button><p>The source will be uploaded and checked before you continue.</p></div>
      {busy === 'source' && <p role="status">Uploading and validating the source…</p>}
    </section> : <section className="wizard-panel" aria-labelledby="documents-heading">
      <div className="section-heading"><h2 id="documents-heading" ref={heading} tabIndex={-1}>Documents and audit</h2><button disabled={!!busy} onClick={editSource}>Back to source</button></div>
      <div className="confirmed-source"><strong>Source confirmed</strong><span>{csv.name}</span><span>{confirmed.reading_count} readings, {confirmed.field_count} fields</span></div>
      <p>Add one or more scanned PDFs. Up to 10 files, 20 MB and 12 pages in total. PDFs are combined into one chart in the order listed.</p>
      <FilePicker key={runKey} kind="pdf" files={pdfs} onChange={changePdfs} disabled={!!busy} multiple/>
      <div className="run-bar document-actions"><button className="primary" disabled={!pdfs.length || !!busy} onClick={processDocuments}>{busy === 'extract' ? 'Processing…' : 'Process'}</button><button className="primary" disabled={!extraction || !confirmed || !!busy} onClick={audit}>{busy === 'audit' ? 'Comparing…' : 'Compare / Audit'}</button><p>{extraction ? 'Compare uploaded values with the confirmed source.' : 'Process the documents to review their information and enable auditing.'}</p></div>
      {busy === 'extract' && <p className="notice" role="status">Processing uploaded documents. This may take several minutes.</p>}
      {busy === 'audit' && <p role="status">Comparing uploaded information with the source…</p>}
      {extraction && <div className="extraction-section"><div className="section-heading"><h3>Uploaded information</h3><p>{extraction.documents.length} documents, {extraction.pages.length} pages, {extraction.documents.reduce((sum, doc) => sum + doc.readings.length, 0)} readings</p><button aria-expanded={showExtraction} onClick={() => setShowExtraction(v => !v)}>{showExtraction ? 'Hide uploaded information' : 'Show uploaded information'}</button></div>
        {extraction.documents.filter(doc => !doc.readings.length).map((doc, i) => <p key={i} className="warning">{doc.name}: no supported readings detected. Inspect this document manually.</p>)}
        {showExtraction && <Review extraction={extraction}/>}
      </div>}
      {report && <section className="audit-report" aria-label="Audit report"><h3>Audit report</h3><Review extraction={extraction} report={report}/></section>}
    </section>}
    {error && <p className="error notice" role="alert">{error}</p>}
    <p className="privacy-note">Files are sent to the server for processing. Uploads and reports are not saved. This demo supports the supplied vital-sign form layout.</p>
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
