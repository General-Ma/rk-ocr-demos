from .ground_truth import normalize


def alignment(readings, truth):
    # Do not infer a slot from a clinical value. Require every timestamp and a
    # consistent, small offset before comparing forms in document order.
    if len(readings) != len(truth['times']):
        return False, 'Form count differs from CSV reading count. Alignment needs review.'
    slots = [r.get('slot_offset') for r in readings]
    expected = [t - truth['minutes'][0] for t in truth['minutes']]
    if all(s is not None for s in slots):
        if slots != expected or len(set(slots)) != len(slots):
            return False, 'Printed form intervals do not match the CSV sequence. Alignment is unresolved.'
        # Require independent time evidence for the baseline; interval headings
        # then identify slots even when an actual time is missing or corrected.
        anchors = sum(r.get('minutes') is not None and abs(r['minutes']-t) <= 10
                      for r, t in zip(readings, truth['minutes']))
        if anchors < min(2, len(readings)):
            return False, 'Printed intervals were read, but actual times do not establish the CSV baseline.'
        return True, f'Sequence aligned by {len(readings)} printed form intervals and {anchors} supporting actual times. No global time offset applied; unreadable actual times remain unverified.'
    actual = [r.get('minutes') for r in readings]
    if any(t is None for t in actual):
        return False, 'One or more handwritten times could not be read. Sequence alignment is unresolved.'
    offsets = [a - b for a, b in zip(actual, truth['minutes'])]
    if len(set(offsets)) != 1 or abs(offsets[0]) > 10:
        return False, 'Times do not establish a consistent offset of at most 10 minutes. Alignment is unresolved.'
    return True, f'Sequence verified using all {len(readings)} timestamps; actual time offset {offsets[0]:+d} minutes. Both times are retained.'


def compare(readings, truth):
    aligned, note = alignment(readings, truth)
    rows = []
    for i in range(max(len(truth['times']), len(readings))):
        reading = readings[i] if i < len(readings) else {}
        for field in truth['fields']:
            expected = field['values'][i] if i < len(truth['times']) else ''
            item = reading.get('fields', {}).get(field['id'], {})
            raw = item.get('text', '')
            observed = item.get('value', raw)
            left, right = normalize(observed, field['id']), normalize(expected, field['id'])
            if not expected.strip():
                status = 'no_ground_truth'
            elif not aligned:
                status = 'unresolved'
            elif not raw:
                status = 'missing_in_ocr'
            elif left is None or right is None or item.get('uncertain'):
                status = 'unresolved'
            else:
                status = 'match' if left == right else 'mismatch'
            rows.append({'id': len(rows), 'reading': i + 1, 'scheduled_time': truth['times'][i] if i < len(truth['times']) else None,
                         'actual_time': reading.get('time'), 'actual_time_text': reading.get('time_text', ''), 'field': field['id'], 'label': field['label'],
                         'ocr_text': raw, 'ocr_value': observed, 'csv_text': expected, 'status': status,
                         'confidence': item.get('confidence'), 'page': reading.get('page'),
                         'bbox': item.get('bbox', reading.get('bbox')), 'location_kind': item.get('location_kind', 'form')})
    return {'rows': rows, 'aligned': aligned, 'alignment_note': note, 'form_count': len(readings)}
