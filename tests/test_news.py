from __future__ import annotations


from koreanpulse.news import classify_industries


class TestClassifyIndustries:
    def test_semiconductor(self):
        tags = classify_industries("삼성전자, HBM 공급 확대")
        assert "semiconductor" in tags

    def test_battery(self):
        tags = classify_industries("LG에너지솔루션, 전고체 배터리 양산 시작")
        assert "battery" in tags

    def test_multi_label(self):
        tags = classify_industries("현대차, 전기차 배터리 합작법인 설립")
        assert "auto" in tags
        assert "battery" in tags

    def test_no_match(self):
        tags = classify_industries("오늘 날씨가 좋습니다")
        assert tags == []

    def test_defense(self):
        tags = classify_industries("한화에어로스페이스, K9 자주포 폴란드 수출")
        assert "defense" in tags

    def test_case_insensitive(self):
        # Korean keywords don't have casing, but English ones might
        tags = classify_industries("AI 반도체 수요 폭증")
        # Both AI and semiconductor keywords present
        assert "ai" in tags
        assert "semiconductor" in tags
