import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bin.review_picker import calc_score


def test_calc_score_reads_total_score():
    r = {
        "code": "000001",
        "name": "平安银行",
        "conclusion": "持有",
        "total_score": 70,
        "grade": "A",
    }
    result = calc_score(r)
    assert result == 70
