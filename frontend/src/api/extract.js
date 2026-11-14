// A single request carries live progress and the final result; no saved job state.
export async function extractDocuments(data, onProgress) {
  const response = await fetch('/api/extract', {
    method: 'POST', body: data, headers: {Accept: 'application/x-ndjson'},
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'The server could not process these documents.');
  }
  if (!response.body || !response.headers.get('content-type')?.includes('application/x-ndjson')) {
    throw new Error('Live progress is unavailable. Restart the updated server and try again.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', result;
  function accept(line) {
    if (!line.trim()) return; // Keepalive while the OCR worker is busy.
    const event = JSON.parse(line);
    if (event.type === 'progress') onProgress(event);
    else if (event.type === 'result') result = event.data;
    else if (event.type === 'error') throw new Error(event.detail);
  }
  try {
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value, {stream: !done});
      let end;
      while ((end = buffer.indexOf('\n')) !== -1) {
        accept(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
      }
      if (done) break;
    }
    if (buffer.trim()) accept(buffer);
    if (!result) throw new Error('Processing stopped before the results arrived. Please try again.');
    return result;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
