"""
API 연결 전 화면 확인용 예시 데이터 생성기.
collect.py 의 실제 처리 과정(해안 필터, 반려동물 장소 매칭, 예보 요약, 점수 계산)을
가짜 API 응답으로 그대로 돌려 docs/data/sites.json 을 만듭니다. demo=true 로 표시됩니다.

실행: python scripts/demo_data.py
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import collect as C  # noqa: E402

random.seed(7)
NOW = datetime.now(C.KST)

CAMPS = [
    # name, do, sigungu, lat, lon, lctCl, animal
    ("꽃지 솔밭 캠핑장", "충청남도", "태안군", 36.497, 126.335, "해변,숲", "가능"),
    ("무창포 바닷가 캠핑장", "충청남도", "보령시", 36.248, 126.536, "해변", "가능(소형견)"),
    ("변산 솔숲 해변 캠핑장", "전북특별자치도", "부안군", 35.676, 126.531, "해변", "가능"),
    ("돌산 바다마루 오토캠핑장", "전라남도", "여수시", 34.640, 127.780, "해변", "가능"),
    ("금오도 비렁길 섬캠핑장", "전라남도", "여수시", 34.520, 127.740, "섬", "가능(소형견)"),
    ("나로도 솔숲 캠핑장", "전라남도", "고흥군", 34.470, 127.460, "해변,숲", "불가능"),
    ("남열 해돋이 캠핑장", "전라남도", "고흥군", 34.560, 127.480, "해변", "가능"),
    ("상주 은모래 캠핑장", "경상남도", "남해군", 34.720, 127.990, "해변", "가능(소형견)"),
    ("죽도 서핑비치 캠핑장", "강원특별자치도", "양양군", 38.000, 128.760, "해변", "가능"),
    ("장호항 바다 캠핑장", "강원특별자치도", "삼척시", 37.290, 129.310, "해변", "가능(소형견)"),
    ("표선 해비치 야영장", "제주특별자치도", "서귀포시", 33.325, 126.840, "해변", "가능"),
    ("협재 솔숲 야영장", "제주특별자치도", "제주시", 33.394, 126.240, "해변,숲", "불가능"),
    ("산속 계곡 캠핑장", "경기도", "가평군", 37.800, 127.500, "계곡", "가능"),  # 해안 아님 → 걸러져야 함
]

PETS = [
    ("꽃지해수욕장 산책 구간", 36.500, 126.338, "12"), ("펫 동반 오션뷰 카페", 36.510, 126.350, "39"),
    ("무창포 해변 산책로", 36.250, 126.538, "12"), ("펫 동반 펜션", 36.258, 126.548, "32"),
    ("변산해수욕장 산책 구간", 35.680, 126.533, "12"),
    ("방죽포 반려견 산책 구간", 34.618, 127.790, "12"), ("바다 앞 펫 동반 카페", 34.648, 127.785, "39"),
    ("비렁길 1코스", 34.525, 127.745, "12"),
    ("남열해돋이해수욕장", 34.563, 127.483, "12"),
    ("상주은모래비치 산책로", 34.722, 127.993, "12"), ("펫 동반 베이커리", 34.735, 127.995, "39"),
    ("죽도해변 산책 구간", 38.002, 128.762, "12"), ("펫 동반 서퍼 카페", 38.006, 128.760, "39"),
    ("장호해변 산책로", 37.292, 129.312, "12"),
    ("표선해수욕장 산책 구간", 33.327, 126.842, "12"), ("펫 동반 감귤밭 카페", 33.340, 126.810, "39"),
]

FISH = [  # 포인트명, lat, lon, 대상어
    ("안면도 남단 갯바위", 36.470, 126.330, "우럭"), ("무창포 선상", 36.240, 126.510, "주꾸미"),
    ("돌산 갯바위", 34.625, 127.790, "감성돔"), ("금오도 남단 선상", 34.490, 127.760, "참돔"),
    ("나로도항 방파제", 34.465, 127.470, "볼락"), ("남열 갯바위", 34.555, 127.490, "무늬오징어"),
    ("상주 앞바다 선상", 34.700, 128.000, "갈치"), ("죽도 방파제", 38.008, 128.765, "가자미"),
    ("장호항 갯바위", 37.285, 129.315, "감성돔"), ("표선 갯바위", 33.320, 126.850, "벵에돔"),
    ("비양도 선상", 33.410, 126.230, "한치"),
]
LEVELS = ["매우좋음", "좋음", "좋음", "보통", "보통", "나쁨"]


def fake_call(url, params, label, retries=2):
    def wrap(items, total=None):
        return {"response": {"header": {"resultCode": "00"},
                             "body": {"items": {"item": items}, "totalCount": total if total is not None else len(items)}}}
    if url == C.CAMPING_URL:
        return wrap([{"contentId": str(i), "facltNm": n, "doNm": d, "sigunguNm": s, "mapY": str(la), "mapX": str(lo),
                      "lctCl": l, "animalCmgCl": a, "sbrsCl": "전기,무선인터넷,장작판매,온수,트렘폴린"[: 6 + i * 3],
                      "addr1": f"{d} {s}", "resveUrl": ""} for i, (n, d, s, la, lo, l, a) in enumerate(CAMPS)])
    if url == C.PET_URL:
        return wrap([{"title": t, "mapy": str(la), "mapx": str(lo), "contenttypeid": ty} for t, la, lo, ty in PETS])
    if url == C.WEATHER_URL:
        items = []
        for d in range(4):
            day = (NOW + timedelta(days=d)).strftime("%Y%m%d")
            rain = random.choice([0, 10, 20, 30, 60])
            wind = random.choice([2, 3, 4, 5, 6, 8])
            for h in range(0, 24):
                hh = f"{h:02d}00"
                vals = {"POP": rain, "WSD": wind + random.choice([-1, 0, 0, 1]), "SKY": random.choice(["1", "1", "3", "4"]),
                        "PTY": "1" if rain >= 60 and h in (14, 15, 16) else "0", "TMP": 17 + (5 if 11 <= h <= 16 else 0),
                        "WAV": round(0.4 + wind * 0.1, 1)}
                items += [{"fcstDate": day, "fcstTime": hh, "category": k, "fcstValue": str(v)} for k, v in vals.items()]
        return wrap(items)
    if url == "FAKE_FISHING":
        if params.get("gubun") != "갯바위":
            return wrap([])
        items = []
        for n, la, lo, f in FISH:
            for d in range(4):
                day = (NOW + timedelta(days=d)).strftime("%Y%m%d")
                items.append({"seafsPstnNm": n, "lat": la, "lot": lo, "predcYmd": day, "totalIndex": random.choice(LEVELS),
                              "seafsTgfshNm": f, "minWtem": round(random.uniform(18, 23), 1), "tdlvHrCn": f"{random.randint(1,14)}물"})
        return wrap(items)
    raise AssertionError(url)


def main():
    C.call = fake_call
    C.save_sample = lambda *a, **k: None
    os.environ["FISHING_URL"] = "FAKE_FISHING"
    camps = C.fetch_camps()
    C.attach_pet_places(camps)
    C.attach_fishing(camps, C.fetch_fishing())
    grids = C.fetch_weather(camps, NOW)
    result = C.build(camps, grids, NOW)
    result["demo"] = True
    os.makedirs(os.path.dirname(C.OUT_PATH), exist_ok=True)
    with open(C.OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print("예시 데이터 저장:", C.OUT_PATH)


if __name__ == "__main__":
    main()
