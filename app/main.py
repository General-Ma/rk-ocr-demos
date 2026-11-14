import asyncio
import multiprocessing
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from .services.pipeline import worker

MAX_BODY = 22 * 1024 * 1024
TIMEOUT_SECONDS = 600


class BodyTooLarge(Exception):
    pass


class BodyLimit:
    """Enforce a bound even when Content-Length is absent or incorrect."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        total = 0
        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get('body', b''))
            if total > MAX_BODY:
                raise BodyTooLarge()
            return message
        async def no_store(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).append((b'cache-control',b'no-store'))
            await send(message)
        try:
            await self.app(scope, bounded_receive, no_store)
        except BodyTooLarge:
            await JSONResponse({'detail':'Upload exceeds the 22 MB request limit.'},status_code=413)(scope,receive,no_store)


app = FastAPI(title='Local OCR chart review', debug=False)
app.add_middleware(BodyLimit)
busy = asyncio.Lock()


@app.get('/api/health')
def health():
    return {'status':'ready', 'processing':busy.locked(), 'ocr':'RapidOCR / ONNX CPU', 'model_initialization':'on first request'}


@app.post('/api/ocr')
async def ocr(request: Request):
    if busy.locked():
        raise HTTPException(409,'Another comparison is running. Try again when it finishes.')
    async with busy:
        # Closing FormData closes every multipart spooled file, including errors.
        async with request.form(max_files=2,max_fields=0,max_part_size=1024*1024) as form:
            pdf, csv = form.get('pdf'),form.get('csv')
            if len(form.multi_items()) != 2 or not isinstance(pdf,UploadFile) or not isinstance(csv,UploadFile):
                raise HTTPException(422,'Upload exactly one PDF (pdf) and one CSV (csv).')
            content = []
            for upload, suffix, limit in ((pdf,'.pdf',20*1024*1024),(csv,'.csv',1024*1024)):
                if not (upload.filename or '').lower().endswith(suffix):
                    raise HTTPException(422,f'Expected a {suffix} file.')
                blob = await upload.read(limit+1)
                if not blob or len(blob)>limit:
                    raise HTTPException(413,f'{suffix.upper()} must be nonempty and at most {limit//1024//1024} MB.')
                content.append(blob)
            if b'%PDF-' not in content[0][:1024]:
                raise HTTPException(422,'The uploaded document is not a PDF.')
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=worker,args=(child,*content),daemon=True)
        try:
            process.start()
            child.close()
            deadline = asyncio.get_running_loop().time()+TIMEOUT_SECONDS
            while not parent.poll():
                if not process.is_alive():
                    raise HTTPException(500,'OCR worker stopped unexpectedly. Try a smaller scan.')
                if asyncio.get_running_loop().time()>deadline:
                    raise HTTPException(504,'OCR exceeded the 10-minute limit. Try fewer pages.')
                if await request.is_disconnected():
                    raise HTTPException(499,'Client disconnected.')
                await asyncio.sleep(.1)
            try:
                status, payload = await asyncio.to_thread(parent.recv)
            except EOFError:
                raise HTTPException(500,'OCR worker stopped before returning a report.') from None
            if status != 'ok':
                raise HTTPException(422 if status=='validation' else 503,payload)
            return payload
        finally:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                await asyncio.to_thread(process.join, 5)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join)
            parent.close()
            child.close()


# A built frontend can be served from the same local origin without Node.
frontend = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
if frontend.is_dir():
    app.mount('/',StaticFiles(directory=frontend,html=True),name='frontend')
