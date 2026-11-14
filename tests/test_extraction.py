import pytest
from app.services.ocr import slot_offset


@pytest.mark.parametrize('title,expected',[
    ('Vital Signs (within 2 hrs of pre-infusion)',0),
    ('Vital Signs 15 min (+15 min) after start of infusion',15),
    ('Vital Signs 1 h (+15 min) after start of infusion',60),
    ('Vital Signs 3 h 45 min (+15 min) after start of infusion',225),
    ('Vital Signs unreadable',None)])
def test_printed_intervals(title,expected):
    assert slot_offset(title)==expected
