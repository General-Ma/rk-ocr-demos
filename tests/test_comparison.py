import pytest
from app.services.ground_truth import parse_csv, normalize
from app.services.compare import compare


def truth(value='75.40'):
    return parse_csv(f'\ufeffReading,10:00 AM\nWeight (kg),{value}\n'.encode())


def reading(text='75.4', minute=605, confidence=.4):
    return {'time':'10:05','minutes':minute,'page':1,'fields':{'weight':{'text':text,'confidence':confidence,'bbox':[.1,.2,.3,.4]}}}


def test_decimal_match_retains_low_confidence_and_originals():
    report=compare([reading()],truth())
    row=report['rows'][0]
    assert report['aligned']
    assert row['status']=='match'
    assert row['confidence']==.4
    assert row['ocr_text']=='75.4' and row['csv_text']=='75.40'


@pytest.mark.parametrize('observed,expected,status', [('76','75','mismatch'),('','75','missing_in_ocr'),('76','','no_ground_truth'),('7S.4','75.4','unresolved')])
def test_comparison_states(observed,expected,status):
    assert compare([reading(observed)],truth(expected))['rows'][0]['status']==status


def test_alignment_missing_time_and_different_count_are_unresolved():
    assert compare([reading(minute=None)],truth())['rows'][0]['status']=='unresolved'
    assert not compare([reading(),reading()],truth())['aligned']
    assert len(compare([reading(),reading()],truth())['rows'])==2
    assert not compare([reading(minute=700)],truth())['aligned']


def test_inconsistent_offset_is_not_forced():
    data=parse_csv(b'Reading,10:00 AM,10:15 AM\nWeight,75,75\n')
    assert not compare([reading(minute=605),reading(minute=621)],data)['aligned']


def test_aliases_quoted_labels_bom_and_blank():
    data=parse_csv(b'\xef\xbb\xbfReading,10:00 AM\n"Blood Pressure (Diasistolic), mmHg",80\nHeart Rate (Systolic) (bpm),72\nTemperature,\n')
    assert [f['id'] for f in data['fields']]==['diastolic','heart_rate','temperature']
    assert data['fields'][2]['values']==['']
    assert normalize(' Y ','performed')==normalize('Yes','performed')


@pytest.mark.parametrize('content',[b'',b'Reading,nope\nWeight,75',b'Reading,10:00 AM\nWeight,75,76',b'Reading,10:00 AM\nUnknown,75',b'Reading,10:00 AM\nWeight,75\nWeight,76',b'Reading,10:00 AM,10:00 AM\nWeight,75,75'])
def test_bad_csv(content):
    with pytest.raises(ValueError): parse_csv(content)


def test_printed_intervals_align_with_variable_or_unreadable_actual_times():
    data=parse_csv(b'Reading,10:00 AM,10:15 AM,10:30 AM\nWeight,75,75,75\n')
    readings=[dict(reading(minute=605),slot_offset=0),dict(reading(minute=615),slot_offset=15),dict(reading(minute=None),slot_offset=30)]
    assert compare(readings,data)['aligned']
    readings[2]['slot_offset']=15
    assert not compare(readings,data)['aligned']


def test_checkboxes_remain_unresolved_even_if_text_matches():
    data=parse_csv(b'Reading,10:00 AM\nClinically Significant?,N\n')
    source={'minutes':605,'fields':{'significant':{'text':'N','uncertain':True}}}
    assert compare([source],data)['rows'][0]['status']=='unresolved'
