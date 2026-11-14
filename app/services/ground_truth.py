import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

FIELDS = ('performed', 'systolic', 'diastolic', 'heart_rate', 'temperature', 'weight', 'significant')


def field_id(label):
    text = label.lower()
    if 'vital' in text and ('performed' in text or 'status' in text):
        return 'performed'
    if 'heart' in text:
        return 'heart_rate'
    if 'dias' in text or 'diast' in text:
        return 'diastolic'
    if 'systolic' in text:
        return 'systolic'
    if 'temp' in text:
        return 'temperature'
    if 'weight' in text:
        return 'weight'
    if 'significant' in text:
        return 'significant'
    raise ValueError(f'Unsupported Source field: {label[:80]}')


def minutes(text):
    for fmt in ('%I:%M %p', '%H:%M'):
        try:
            t = datetime.strptime(text.strip().upper(), fmt)
            return t.hour * 60 + t.minute
        except ValueError:
            pass
    raise ValueError('Source reading times must use HH:MM or H:MM AM/PM.')


def parse_csv(content):
    try:
        matrix = list(csv.reader(io.StringIO(content.decode('utf-8-sig')), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError('Source must be a valid UTF-8 comma-separated file.') from exc
    matrix = [row for row in matrix if any(cell.strip() for cell in row)]
    if len(matrix) < 2 or not 2 <= len(matrix[0]) <= 65:
        raise ValueError('Source needs a header with 1–64 reading times and field rows.')
    times = [cell.strip() for cell in matrix[0][1:]]
    time_minutes = [minutes(t) for t in times]
    if any(b <= a for a, b in zip(time_minutes, time_minutes[1:])):
        raise ValueError('Source reading times must be unique and in increasing order within one day.')
    fields = []
    seen = set()
    for row in matrix[1:]:
        if len(row) != len(matrix[0]):
            raise ValueError('Every Source row must have the same number of cells as the header; use empty cells for missing values.')
        key = field_id(row[0])
        if key in seen:
            raise ValueError('Source contains a duplicate field.')
        seen.add(key)
        fields.append({'id': key, 'label': row[0], 'values': row[1:]})
    return {'times': times, 'minutes': time_minutes, 'fields': fields}


def normalize(value, key):
    text = value.strip().lower()
    if key in ('performed', 'significant'):
        return {'y': 'yes', 'yes': 'yes', 'n': 'no', 'no': 'no'}.get(text)
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
