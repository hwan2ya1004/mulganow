# -*- coding: utf-8 -*-
"""
test_helpers.py
----------------
핵심 순수 함수(가격 파싱, 절기 판정, 카테고리 매칭 등)에 대한 유닛 테스트.

기존 test_*.py 파일들(test_adpick.py, test_filter.py 등)은 실제 외부 API를
호출하는 수동 점검 스크립트라 API 키·네트워크가 없으면 실행할 수 없습니다.
이 파일은 그와 달리 외부 API 호출이 없는 "순수 로직"만 검증하므로, API 키나
네트워크 연결 없이도 아무 환경에서나 바로 실행할 수 있습니다.

실행 방법:
    python -m unittest test_helpers -v
"""
import unittest
from datetime import date
from unittest.mock import patch

import app
import consumer_price_client as cpc
import generate_blog_post as gbp


# ---------------------------------------------------------------------------
# app.py: 표시명 변환 / 단위 힌트 / 중량 파싱·필터링 / 응답 가공
# ---------------------------------------------------------------------------
class TestDisplayName(unittest.TestCase):
    def test_known_keyword_replaced(self):
        self.assertEqual(app._apply_display_name("참다래/그린 뉴질랜드"), "키위/그린 뉴질랜드")
        self.assertEqual(app._apply_display_name("쇠고기/등심"), "소고기/등심")
        self.assertEqual(app._apply_display_name("계란"), "달걀")

    def test_unknown_name_unchanged(self):
        self.assertEqual(app._apply_display_name("사과/후지"), "사과/후지")

    def test_empty_input(self):
        self.assertEqual(app._apply_display_name(""), "")
        self.assertIsNone(app._apply_display_name(None))


class TestUnitHint(unittest.TestCase):
    def test_known_combo(self):
        self.assertEqual(app._get_unit_hint("배추", "1포기"), "약 2~3kg")
        self.assertEqual(app._get_unit_hint("사과", "10개"), "개당 약 250~350g")

    def test_kg_unit_returns_none_hint(self):
        # kg 단위는 이미 중량이 명확하므로 힌트가 None이어야 함
        self.assertIsNone(app._get_unit_hint("배추", "10kg"))

    def test_unknown_combo_returns_none(self):
        self.assertIsNone(app._get_unit_hint("배추", "999kg"))
        self.assertIsNone(app._get_unit_hint("", "1개"))
        self.assertIsNone(app._get_unit_hint("배추", ""))


class TestParseWeightG(unittest.TestCase):
    def test_kg(self):
        self.assertEqual(app._parse_weight_g("20kg"), 20000)
        self.assertEqual(app._parse_weight_g("1.5kg"), 1500)

    def test_g(self):
        self.assertEqual(app._parse_weight_g("500g"), 500)

    def test_g_does_not_match_gram_word_boundary(self):
        # "gr" 뒤에 다른 글자가 오는 경우 오탐(예: "1kg" 다음의 다른 단위)이 없어야 함
        self.assertIsNone(app._parse_weight_g("1개"))

    def test_unrecognized_returns_none(self):
        self.assertIsNone(app._parse_weight_g("abc"))
        self.assertIsNone(app._parse_weight_g(""))
        self.assertIsNone(app._parse_weight_g(None))


class TestFilterByWeight(unittest.TestCase):
    def test_filters_out_of_range_titles(self):
        items = [
            {"title": "쌀 20kg 상품A"},   # 기준(20kg) 그대로 -> 통과
            {"title": "쌀 15kg 상품B"},   # 0.4~3배 범위(8kg~60kg) 내 -> 통과
            {"title": "쌀 2kg 상품C"},    # 범위 밖(8kg 미만) -> 제외
            {"title": "쌀 소포장 상품D"},  # 중량 표기 없음 -> 통과(허용)
        ]
        result = app._filter_by_weight(items, "20kg")
        titles = {it["title"] for it in result}
        self.assertIn("쌀 20kg 상품A", titles)
        self.assertIn("쌀 15kg 상품B", titles)
        self.assertIn("쌀 소포장 상품D", titles)
        self.assertNotIn("쌀 2kg 상품C", titles)

    def test_non_weight_unit_skips_filtering(self):
        items = [{"title": "아무 상품"}, {"title": "또 다른 상품"}]
        # kamis_unit이 중량이 아니면(예: "1개") 필터링을 적용하지 않고 원본 그대로 반환
        result = app._filter_by_weight(items, "1개")
        self.assertEqual(result, items)

    def test_min_two_results_fallback(self):
        # 필터링 후 결과가 2개 미만이면 원본을 그대로 반환(과도한 필터링 방지)
        items = [{"title": "쌀 1kg 상품A"}, {"title": "쌀 1kg 상품B"}]
        result = app._filter_by_weight(items, "20kg")
        self.assertEqual(result, items)


class TestNormalizeItem(unittest.TestCase):
    def test_basic_fields_and_change_pct(self):
        raw = {
            "item_name": "참다래/그린 뉴질랜드",
            "item_code": "312",
            "unit": "1개",
            "category_code": "400",
            "category_name": "과일류",
            "dpr1": "1,200",
            "dpr2": "1,150",
            "dpr3": "1,000",
            "dpr4": "900",
            "kind_name": "00",
            "rank_name": "",
        }
        result = app._normalize_item(raw)
        self.assertEqual(result["item_name"], "키위/그린 뉴질랜드")
        self.assertEqual(result["today_price"], 1200)
        self.assertEqual(result["day_ago_price"], 1150)
        self.assertEqual(result["month_ago_price"], 1000)
        self.assertEqual(result["year_ago_price"], 900)
        # (1200 - 1000) / 1000 * 100 = 20.0
        self.assertEqual(result["month_change_pct"], 20.0)
        self.assertEqual(result["unit_hint"], "약 80~120g")  # 키위 원본명("참다래") 1개 힌트

    def test_kind_and_rank_suffix_appended(self):
        raw = {
            "item_name": "마른멸치/마른멸치",
            "dpr1": "10000",
            "kind_name": "대",
            "rank_name": "특",
        }
        result = app._normalize_item(raw)
        self.assertIn("(대/특)", result["item_name"])

    def test_skip_meaningless_kind_rank(self):
        raw = {
            "item_name": "사과/후지",
            "dpr1": "5000",
            "kind_name": "00",
            "rank_name": "평균",
        }
        result = app._normalize_item(raw)
        # "00"/"평균"은 의미 없는 기본값이므로 접미사가 붙지 않아야 함
        self.assertEqual(result["item_name"], "사과/후지")

    def test_missing_month_ago_no_change_pct(self):
        raw = {"item_name": "무", "dpr1": "1000"}
        result = app._normalize_item(raw)
        self.assertIsNone(result["month_change_pct"])

    def test_invalid_price_string_becomes_none(self):
        raw = {"item_name": "무", "dpr1": "-", "dpr3": "n/a"}
        result = app._normalize_item(raw)
        self.assertIsNone(result["today_price"])
        self.assertIsNone(result["month_ago_price"])


class TestExtractItems(unittest.TestCase):
    def test_price_list(self):
        raw = {"price": [{"a": 1}, {"a": 2}]}
        self.assertEqual(app._extract_items(raw), [{"a": 1}, {"a": 2}])

    def test_price_dict_wrapped_in_list(self):
        raw = {"price": {"a": 1}}
        self.assertEqual(app._extract_items(raw), [{"a": 1}])

    def test_data_item_fallback(self):
        raw = {"data": {"item": [{"a": 1}]}}
        self.assertEqual(app._extract_items(raw), [{"a": 1}])

    def test_non_dict_returns_empty(self):
        self.assertEqual(app._extract_items(None), [])
        self.assertEqual(app._extract_items("oops"), [])

    def test_no_recognizable_shape_returns_empty(self):
        self.assertEqual(app._extract_items({"unexpected": "shape"}), [])


class TestExtractTrendPoints(unittest.TestCase):
    def test_normal_points_sorted_by_date(self):
        raw = {"data": {"item": [
            {"regday": "2024/01/02", "price": "1,200"},
            {"regday": "2024/01/01", "price": "1,000"},
        ]}}
        points = app._extract_trend_points(raw)
        self.assertEqual(points, [
            {"date": "2024/01/01", "price": 1000},
            {"date": "2024/01/02", "price": 1200},
        ])

    def test_error_response_returns_empty(self):
        self.assertEqual(app._extract_trend_points({"data": "-1"}), [])
        self.assertEqual(app._extract_trend_points({"data": None}), [])

    def test_dash_price_skipped(self):
        raw = {"data": {"item": [{"regday": "2024/01/01", "price": "-"}]}}
        self.assertEqual(app._extract_trend_points(raw), [])

    def test_non_dict_raw_returns_empty(self):
        self.assertEqual(app._extract_trend_points(None), [])
        self.assertEqual(app._extract_trend_points("oops"), [])


# ---------------------------------------------------------------------------
# consumer_price_client.py: 최근 금요일 판정 / XML 파싱
# ---------------------------------------------------------------------------
class TestGetLatestFriday(unittest.TestCase):
    def _run_for(self, year, month, day):
        fixed_today = date(year, month, day)
        with patch("consumer_price_client.date") as mock_date:
            mock_date.today.return_value = fixed_today
            result = cpc.get_latest_friday()
        result_date = date(int(result[:4]), int(result[4:6]), int(result[6:8]))
        return fixed_today, result_date

    def test_returns_friday_on_or_before_today_within_a_week(self):
        # 2024-01-01(월) ~ 2024-01-07(일) 한 주 전체(요일 7개 전부)를 점검
        for day in range(1, 8):
            fixed_today, result_date = self._run_for(2024, 1, day)
            with self.subTest(day=day):
                self.assertEqual(result_date.weekday(), 4, "결과가 금요일이 아님")
                self.assertLessEqual(result_date, fixed_today)
                self.assertLessEqual((fixed_today - result_date).days, 6)

    def test_today_is_friday_returns_today(self):
        # 2024-01-05는 금요일
        fixed_today, result_date = self._run_for(2024, 1, 5)
        self.assertEqual(result_date, fixed_today)


class TestParseXml(unittest.TestCase):
    def test_item_list_structure(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <response>
          <result>
            <item><goodId>1</goodId><goodName>테스트상품</goodName></item>
            <item><goodId>2</goodId><goodName>상품2</goodName></item>
          </result>
        </response>"""
        items = cpc._parse_xml(xml)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["goodName"], "테스트상품")

    def test_dotted_tag_structure(self):
        # 가격 정보 응답은 태그명에 점(.)이 포함됨
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <response>
          <result>
            <iros.openapi.service.vo.goodPriceVO>
              <goodId>1</goodId><goodPrice>1000</goodPrice>
            </iros.openapi.service.vo.goodPriceVO>
          </result>
        </response>"""
        items = cpc._parse_xml(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["goodPrice"], "1000")

    def test_error_code_raises(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <response><resultCode>30</resultCode><resultMsg>err</resultMsg></response>"""
        with self.assertRaises(cpc.ConsumerPriceApiError):
            cpc._parse_xml(xml)

    def test_ok_code_with_no_result_returns_empty(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <response><resultCode>00</resultCode></response>"""
        self.assertEqual(cpc._parse_xml(xml), [])

    def test_invalid_xml_raises(self):
        with self.assertRaises(cpc.ConsumerPriceApiError):
            cpc._parse_xml("not xml at all <<<")


# ---------------------------------------------------------------------------
# generate_blog_post.py: 절기 판정 / 카테고리 매칭 / 다양성 가드 / 슬러그
# ---------------------------------------------------------------------------
class TestActiveSeasonalEvents(unittest.TestCase):
    def test_date_event_within_lead_days(self):
        # "초복" date=2026-07-15, lead_days=5 -> 2026-07-10~2026-07-15 활성
        events = gbp.active_seasonal_events(today=date(2026, 7, 12))
        names = {e["name"] for e in events}
        self.assertIn("초복", names)

    def test_date_event_outside_lead_days_not_active(self):
        events = gbp.active_seasonal_events(today=date(2026, 6, 1))
        names = {e["name"] for e in events}
        self.assertNotIn("초복", names)

    def test_date_event_after_event_day_not_active(self):
        # lead_days는 사전(미래) 기간만 포함하므로, 당일이 지나면 비활성이어야 함
        events = gbp.active_seasonal_events(today=date(2026, 7, 16))
        names = {e["name"] for e in events}
        self.assertNotIn("초복", names)

    def test_date_event_on_the_day_is_active(self):
        events = gbp.active_seasonal_events(today=date(2026, 7, 15))
        names = {e["name"] for e in events}
        self.assertIn("초복", names)

    def test_range_event_active_within_period(self):
        # "장마" start=2026-06-19, end=2026-07-25
        events = gbp.active_seasonal_events(today=date(2026, 7, 21))
        names = {e["name"] for e in events}
        self.assertIn("장마", names)

    def test_range_event_inactive_outside_period(self):
        events = gbp.active_seasonal_events(today=date(2026, 8, 1))
        names = {e["name"] for e in events}
        self.assertNotIn("장마", names)


class TestConsumerCategoryName(unittest.TestCase):
    def test_known_code(self):
        self.assertEqual(gbp.consumer_category_name("030102"), "채소·농산물")

    def test_unknown_code_returns_default(self):
        self.assertEqual(gbp.consumer_category_name("999999"), "기타")

    def test_empty_code_returns_default(self):
        self.assertEqual(gbp.consumer_category_name(""), "기타")
        self.assertEqual(gbp.consumer_category_name(None), "기타")


class TestCleanConsumerName(unittest.TestCase):
    def test_strips_trailing_parenthetical(self):
        self.assertEqual(gbp.clean_consumer_name("대표 세숫비누(1kg)"), "대표 세숫비누")

    def test_no_parenthetical_unchanged(self):
        self.assertEqual(gbp.clean_consumer_name("대표 세숫비누"), "대표 세숫비누")

    def test_empty_input(self):
        self.assertEqual(gbp.clean_consumer_name(""), "")
        self.assertEqual(gbp.clean_consumer_name(None), "")


class TestDiversifyByCategory(unittest.TestCase):
    def test_caps_per_category_then_backfills(self):
        candidates = [
            {"name": "A1", "cat": "채소"},
            {"name": "A2", "cat": "채소"},
            {"name": "A3", "cat": "채소"},
            {"name": "B1", "cat": "과일"},
        ]
        result = gbp._diversify_by_category(
            candidates, n=3, max_per_category=1, category_of=lambda c: c["cat"]
        )
        names = [c["name"] for c in result]
        # 카테고리당 1개 상한 -> 먼저 A1, B1을 채우고, 부족분은 뒤로 미뤄뒀던 A2로 백필
        self.assertEqual(names, ["A1", "B1", "A2"])

    def test_returns_up_to_n_items(self):
        candidates = [{"name": str(i), "cat": "x"} for i in range(10)]
        result = gbp._diversify_by_category(
            candidates, n=3, max_per_category=10, category_of=lambda c: c["cat"]
        )
        self.assertEqual(len(result), 3)


class TestSlugifyDatePrefixed(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        slug = gbp.slugify_date_prefixed("Price Watch!!")
        self.assertTrue(slug.endswith("-price-watch"))
        self.assertRegex(slug, r"^\d{4}-\d{2}-\d{2}-price-watch$")

    def test_collapses_repeated_hyphens(self):
        slug = gbp.slugify_date_prefixed("a---b")
        self.assertTrue(slug.endswith("-a-b"))


if __name__ == "__main__":
    unittest.main()
