"""Layout-specific OCR. Expected values never enter this module."""
import re
from rapidocr import RapidOCR
import onnxruntime


def make_engine():
    onnxruntime.disable_telemetry_events()
    return RapidOCR(params={'Global.log_level': 'error', 'Global.text_score': 0.3,
                            'EngineConfig.onnxruntime.intra_op_num_threads': 4,
                            'EngineConfig.onnxruntime.inter_op_num_threads': 2})


def tokens(engine, image):
    result = engine(image)
    if result.boxes is None:
        return []
    height, width = image.shape[:2]
    return [{'text': text, 'confidence': float(score),
             'bbox': [float(box[:,0].min()/width), float(box[:,1].min()/height),
                      float(box[:,0].max()/width), float(box[:,1].max()/height)]}
            for box, text, score in zip(result.boxes, result.txts, result.scores)]


def center(token):
    b = token['bbox']
    return (b[0]+b[2])/2, (b[1]+b[3])/2


def slot_offset(title):
    text = title.lower().split('(+')[0]
    if 'pre-infusion' in text:
        return 0
    hours = re.search(r'(\d+)\s*h\b', text)
    mins = re.search(r'(\d+)\s*min\b', text)
    if not hours and not mins:
        return None
    return (int(hours.group(1))*60 if hours else 0) + (int(mins.group(1)) if mins else 0)


def extract_page(engine, image, page):
    words = tokens(engine, image)
    headers = sorted([t for t in words if re.search(r'vital\s*signs', t['text'], re.I)], key=lambda t:center(t)[1])
    readings = []
    for index, header in enumerate(headers):
        top = header['bbox'][3]
        bottom = headers[index+1]['bbox'][1] if index+1 < len(headers) else min(.97, top + .24)
        group = [t for t in words if top < center(t)[1] < bottom]
        def anchor(pattern):
            return next((t for t in group if re.search(pattern, t['text'], re.I)), None)
        time_label, bp, heart, temp, weight = (anchor(p) for p in ('time.*vitals', 'blood.*pressure', 'heart.*rate', r'temp.*\(.*c', 'weight.*kg'))
        # A title without the core printed labels is still represented, but not
        # silently paired with data from another form.
        reading = {'page':page, 'bbox':[.12,header['bbox'][1],.88,min(bottom,.97)], 'fields':{}, 'time':None, 'time_text':'', 'minutes':None, 'slot_offset':slot_offset(header['text'])}
        if not all((time_label,bp,heart,temp,weight)):
            readings.append(reading)
            continue
        x0, x1, x2 = bp['bbox'][0], heart['bbox'][0], temp['bbox'][0]
        column = x2 - x1
        right = min(.98,x2 + column)
        # Printed labels are the coordinate anchors; no sample-specific values
        # or page-specific coordinates are used.
        regions = {
            'time': [time_label['bbox'][0],time_label['bbox'][3],right,min(bp['bbox'][1],temp['bbox'][1])],
            'pressure': [x0,bp['bbox'][3],x1,bottom],
            'heart_rate': [x1,heart['bbox'][3],x2,bottom],
            'temperature': [x2,temp['bbox'][3],right,weight['bbox'][1]],
            'weight': [x2,weight['bbox'][3],right,bottom],
        }
        def read_region(key):
            region = regions[key]
            found = [t for t in group if region[0] <= center(t)[0] < region[2] and region[1] <= center(t)[1] < region[3]
                     and re.search(r'\d', t['text']) and not re.search(r'[a-zA-Z]{2,}', t['text'])]
            if len(found) != 1:
                return {'text':' '.join(t['text'] for t in found), 'bbox':region, 'confidence':None, 'uncertain':bool(found), 'location_kind':'expected'}
            return {**found[0], 'location_kind':'detected'}
        time = read_region('time')
        reading['time_text'] = time['text']
        compact = re.sub(r'\s','',time['text']).replace('.',':')
        match = re.fullmatch(r'(\d{1,2}):?(\d{2})',compact)
        if match and not time.get('uncertain') and (time.get('confidence') or 0) >= .8:
            hour, minute = map(int,match.groups())
            if hour < 24 and minute < 60:
                reading.update(time=f'{hour:02}:{minute:02}', minutes=hour*60+minute)
        pressure = read_region('pressure')
        pair = re.fullmatch(r'\s*(\d{2,3})\s*/\s*(\d{2,3})\s*',pressure['text'])
        for key, position in [('systolic',1),('diastolic',2)]:
            reading['fields'][key] = {**pressure, 'value':pair.group(position) if pair else '', 'uncertain':not bool(pair)}
        for key in ('heart_rate','temperature','weight'):
            reading['fields'][key] = read_region(key)
        # OCR recognizes the printed checkbox labels, not reliably the ticks.
        # Explicitly unresolved instead of assuming the usual Yes/No answers.
        for key, region in [('performed',[x0,top,x2,bp['bbox'][1]]),('significant',[right,top,min(.98,right+column),bottom])]:
            reading['fields'][key] = {'text':'Checkbox: inspect source', 'value':'', 'confidence':None, 'uncertain':True, 'bbox':region,'location_kind':'expected'}
        if time['text'] or any(reading['fields'][key]['text'] for key in ('systolic','heart_rate','temperature','weight')):
            readings.append(reading)
    return readings
