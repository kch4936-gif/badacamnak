"""
주말 바다캠낚 데이터 수집기

매일 GitHub Actions에서 실행되어 아래 순서로 docs/data/sites.json 을 만듭니다.
  1. 고캠핑 API     → 전국 캠핑장 중 입지가 '해변' 또는 '섬'인 곳만 고르기
  2. 반려동물 동반여행 API → 동반 가능 장소 목록을 받아 캠핑장별 가까운 곳 3개 찾기
  3. 기상청 단기예보 API → 캠핑장 좌표를 예보 격자로 바꿔, 격자당 한 번만 호출
  4. 바다낚시지수 API → FISHING_URL 이 설정돼 있을 때만 사용 (없으면 낚시 점수 제외)
  5. 날짜별 점수 계산 후 JSON 저장

인증키는 환경변수 DATA_GO_KR_KEY 에서 읽습니다. 코드나 결과 파일에는 절대 저장하지 않습니다.
표준 라이브러리만 사용하므로 별도 설치가 필요 없습니다.
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "docs", "data", "sites.json")
SAMPLE_DIR = os.path.join(ROOT, "samples")

APP_NAME = "badacamnak"
CAMPING_URL = "https://apis.data.go.kr/B551011/GoCamping/basedList"
PET_URL = "https://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
WEATHER_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
FISHING_URL = "https://apis.data.go.kr/1192136/fcstFishingv2/GetFcstFishingApiServicev2"
FISHING_GUBUN = ("갯바위", "선상")

COASTAL_LOCATIONS = ("해변", "섬")
PET_RADIUS_KM = 10
FISH_MAX_KM = 15
FISH_POINTS = {5: 40, 4: 32, 3: 24, 2: 14, 1: 6}
FISH_LEVEL = {"매우좋음": 5, "좋음": 4, "보통": 3, "나쁨": 2, "매우나쁨": 1}

# 전남은 서해안·남해안이 섞여 있어 시군 단위로 나눈다
JEONNAM_WEST = ("영광", "함평", "무안", "목포", "신안")


GATEWAY_ERRORS = ("SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "SERVICE_ACCESS_DENIED_ERROR",
                  "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR", "SERVICE_TIMEOUT_ERROR")


class ApiError(Exception):
    pass


# ───────────────────────── 공통 호출 ─────────────────────────

def service_key():
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        sys.exit("DATA_GO_KR_KEY 환경변수가 비어 있습니다. GitHub 저장소 Settings → Secrets 에 인증키를 넣어 주세요.")
    # 포털의 'Encoding' 키를 넣었어도 동작하도록 한 번 풀어 둔다 (아래에서 다시 인코딩함)
    return urllib.parse.unquote(key)


def call(url, params, label, retries=2):
    query = urllib.parse.urlencode({"serviceKey": service_key(), **params})
    full = f"{url}?{query}"
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(full, timeout=30) as res:
                raw = res.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            # 게이트웨이는 인증 오류를 HTTP 403 등과 함께 본문(JSON/XML)으로 알려준다
            raw = e.read().decode("utf-8", errors="replace")
            if any(code in raw for code in GATEWAY_ERRORS):
                break
            last = f"HTTP {e.code}"
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise ApiError(f"{label}: 연결 실패 ({last})")

    # 공공데이터포털 게이트웨이 오류 (XML 또는 OpenAPI_ServiceResponse JSON)
    for code in GATEWAY_ERRORS:
        if code in raw:
            raise ApiError(f"{label}: {code}")
    if raw.lstrip().startswith("<"):
        raise ApiError(f"{label}: JSON이 아닌 응답 → {raw[:200]}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError(f"{label}: JSON 해석 실패 → {raw[:200]}")

    if "response" not in data and "header" in data:
        data = {"response": data}  # 바다낚시지수처럼 response 감싸기 없이 오는 API 대응
    header = data.get("response", {}).get("header", {})
    code = str(header.get("resultCode", "00"))
    if code not in ("00", "0000", "0"):
        if code == "03":  # NODATA
            return data
        raise ApiError(f"{label}: resultCode={code} {header.get('resultMsg')}")
    return data


def items_of(data):
    body = data.get("response", {}).get("body", {}) or {}
    items = body.get("items") or {}
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return items or [], int(body.get("totalCount") or 0)


def save_sample(name, data):
    """API 응답 구조 확인용 샘플(앞부분만). 인증키는 응답에 들어있지 않다."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    trimmed = json.loads(json.dumps(data))
    try:
        body = trimmed["response"]["body"]
        it = body["items"]["item"] if isinstance(body["items"], dict) else body["items"]
        if isinstance(it, list):
            if isinstance(body["items"], dict):
                body["items"]["item"] = it[:3]
            else:
                body["items"] = it[:3]
    except (KeyError, TypeError):
        pass
    with open(os.path.join(SAMPLE_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=1)


def paged(url, base_params, label, rows=1000, sample=None):
    out, page = [], 1
    while True:
        data = call(url, {**base_params, "numOfRows": rows, "pageNo": page}, f"{label} p{page}")
        if page == 1 and sample:
            save_sample(sample, data)
        items, total = items_of(data)
        out.extend(items)
        if not items or len(out) >= total:
            return out
        page += 1
        time.sleep(0.2)


# ───────────────────────── 지리 계산 ─────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_grid(lat, lon):
    """위경도 → 기상청 단기예보 격자(nx, ny). 기상청 제공 LCC 변환식."""
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    s1, s2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(
        math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5))
    sf = math.tan(math.pi * 0.25 + s1 * 0.5) ** sn * math.cos(s1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re * sf / math.tan(math.pi * 0.25 + lat * D * 0.5) ** sn
    theta = lon * D - olon
    if theta > math.pi:
        theta -= 2 * math.pi
    if theta < -math.pi:
        theta += 2 * math.pi
    theta *= sn
    nx = math.floor(ra * math.sin(theta) + XO + 0.5)
    ny = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def zone_of(do, sigungu):
    do = do or ""
    sg = sigungu or ""
    if "제주" in do:
        return "제주"
    if any(k in do for k in ("강원", "경북", "경상북", "울산")):
        return "동해"
    if any(k in do for k in ("부산", "경남", "경상남")):
        return "남해"
    if "전남" in do or "전라남" in do:
        return "서해" if any(k in sg for k in JEONNAM_WEST) else "남해"
    return "서해"  # 인천·경기·충남·전북


SHORT_DO = {"경기": "경기", "인천": "인천", "충청남": "충남", "충남": "충남", "전북": "전북", "전라북": "전북",
            "전라남": "전남", "전남": "전남", "경상남": "경남", "경남": "경남", "경상북": "경북", "경북": "경북",
            "강원": "강원", "부산": "부산", "울산": "울산", "제주": "제주", "서울": "서울", "충청북": "충북", "충북": "충북"}


def short_do(do):
    do = do or ""
    for k, v in SHORT_DO.items():
        if do.startswith(k):
            return v
    return do


# ───────────────────────── 1. 캠핑장 ─────────────────────────

def pet_policy(raw):
    raw = (raw or "").strip()
    if not raw or "불가" in raw:
        return "none"
    if "소형" in raw:
        return "small"
    if "가능" in raw:
        return "all"
    return "none"


def fetch_camps():
    items = paged(CAMPING_URL, {"MobileOS": "ETC", "MobileApp": APP_NAME, "_type": "json"},
                  "고캠핑", sample="camping")
    camps = []
    for it in items:
        loc = it.get("lctCl") or ""
        if not any(k in loc for k in COASTAL_LOCATIONS):
            continue
        try:
            lat, lon = float(it.get("mapY")), float(it.get("mapX"))
        except (TypeError, ValueError):
            continue
        sbrs = [s for s in (it.get("sbrsCl") or "").split(",") if s]
        camps.append({
            "id": str(it.get("contentId")),
            "name": it.get("facltNm", "").strip(),
            "zone": zone_of(it.get("doNm"), it.get("sigunguNm")),
            "city": (it.get("sigunguNm") or "").strip(),
            "area": f"{short_do(it.get('doNm'))} {it.get('sigunguNm') or ''}".strip(),
            "addr": it.get("addr1", ""),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "loc": loc,
            "pet": pet_policy(it.get("animalCmgCl")),
            "petRaw": it.get("animalCmgCl") or "",
            "fac": min(20, 8 + len(sbrs) * 2),
            "tel": it.get("tel") or "",
            "link": it.get("resveUrl") or it.get("homepage") or "",
            "img": it.get("firstImageUrl") or "",
            "intro": (it.get("lineIntro") or "").strip(),
        })
    print(f"고캠핑: 전체 {len(items)}곳 중 해안(해변·섬) {len(camps)}곳")
    return camps


# ───────────────────────── 2. 반려동물 동반 장소 ─────────────────────────

PET_TYPE = {"12": "관광지", "14": "문화시설", "28": "레포츠", "32": "숙소", "38": "쇼핑", "39": "음식점·카페"}


def attach_pet_places(camps):
    try:
        items = paged(PET_URL, {"MobileOS": "ETC", "MobileApp": APP_NAME, "_type": "json", "arrange": "C"},
                      "반려동물 동반여행", sample="pet")
    except ApiError as e:
        print(f"⚠ 반려동물 동반 장소를 건너뜁니다: {e}")
        return
    places = []
    for it in items:
        try:
            places.append((float(it["mapy"]), float(it["mapx"]), it.get("title", ""),
                           PET_TYPE.get(str(it.get("contenttypeid")), "장소")))
        except (KeyError, TypeError, ValueError):
            continue
    print(f"반려동물 동반 장소 {len(places)}곳")
    for c in camps:
        near = []
        for lat, lon, title, kind in places:
            if abs(lat - c["lat"]) > 0.12 or abs(lon - c["lon"]) > 0.15:
                continue
            d = haversine(c["lat"], c["lon"], lat, lon)
            if d <= PET_RADIUS_KM:
                near.append([kind, title, round(d, 1)])
        c["near"] = sorted(near, key=lambda x: x[2])[:3]


# ───────────────────────── 3. 날씨 ─────────────────────────

def latest_base(now):
    """가장 최근에 발표된 단기예보 기준시각 (발표 후 15분 여유)."""
    for back in range(0, 30):
        t = now - timedelta(hours=back)
        if t.hour in (2, 5, 8, 11, 14, 17, 20, 23):
            cand = t.replace(minute=0, second=0, microsecond=0)
            if now - cand >= timedelta(minutes=15):
                return cand
    raise RuntimeError("기준시각 계산 실패")


SKY = {"1": "맑음", "3": "구름 많음", "4": "흐림"}
PTY = {"1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}


def summarize_day(hours):
    """하루치 시간별 값 → 낮(06~21시) 기준 요약과 오전/오후/밤 슬롯."""
    day = {h: v for h, v in hours.items() if 6 <= int(h[:2]) <= 21}
    if len(day) < 12:
        return None  # 저녁 실행 때의 '오늘'처럼 낮 시간이 대부분 지나간 날은 빼기

    def nums(cat):
        out = []
        for v in day.values():
            try:
                out.append(float(v[cat]))
            except (KeyError, ValueError, TypeError):
                pass
        return out

    pop, wsd, wav, tmp = nums("POP"), nums("WSD"), nums("WAV"), nums("TMP")

    def sky_at(hh):
        v = hours.get(hh) or {}
        if v.get("PTY") and v["PTY"] != "0":
            return PTY.get(v["PTY"], "강수")
        return SKY.get(v.get("SKY"), "-")

    def slot(name, hh):
        v = hours.get(hh) or {}
        return [name, sky_at(hh), f"바람 {v.get('WSD', '-')}m/s"]

    return {
        "rain": int(max(pop)) if pop else 0,
        "wind": round(max(wsd), 1) if wsd else 0,
        "wave": round(max(wav), 1) if wav else None,
        "tmax": round(max(tmp)) if tmp else None,
        "tmin": round(min(tmp)) if tmp else None,
        "slots": [slot("오전", "0900"), slot("오후", "1500"), slot("밤", "2100")],
    }


def fetch_weather(camps, now):
    base = latest_base(now)
    params = {"dataType": "JSON", "base_date": base.strftime("%Y%m%d"), "base_time": base.strftime("%H%M")}
    grids = {}
    for c in camps:
        c["grid"] = to_grid(c["lat"], c["lon"])
        grids.setdefault(c["grid"], None)
    print(f"단기예보 기준 {params['base_date']} {params['base_time']} · 격자 {len(grids)}곳 호출")

    first = True
    for i, (nx, ny) in enumerate(grids):
        try:
            data = call(WEATHER_URL, {**params, "nx": nx, "ny": ny, "numOfRows": 2000, "pageNo": 1},
                        f"단기예보 {nx},{ny}")
        except ApiError as e:
            print(f"⚠ {e}")
            continue
        if first:
            save_sample("weather", data)
            first = False
        items, _ = items_of(data)
        by_day = defaultdict(lambda: defaultdict(dict))
        for it in items:
            by_day[it["fcstDate"]][it["fcstTime"]][it["category"]] = it["fcstValue"]
        grids[(nx, ny)] = {d: summarize_day(h) for d, h in by_day.items()}
        if i % 20 == 19:
            time.sleep(0.5)
    return grids


# ───────────────────────── 4. 낚시지수 (선택) ─────────────────────────

def fetch_fishing():
    """
    국립해양조사원 바다낚시지수(fcstFishingv2). 갯바위·선상 두 구분을 모두 받아 합친다.
    FISHING_URL / FISHING_PARAMS / FISHING_FIELDS 환경변수로 덮어쓸 수 있다 (FISHING_URL=off 면 끔).
    """
    url = os.environ.get("FISHING_URL", "").strip() or FISHING_URL
    if url.lower() == "off":
        print("낚시지수: 꺼짐 → 낚시 점수 없이 계산")
        return []
    extra = json.loads(os.environ.get("FISHING_PARAMS", "{}") or "{}")
    items = []
    for gubun in FISHING_GUBUN:
        try:
            items += paged(url, {"type": "json", "gubun": gubun, **extra}, f"바다낚시지수({gubun})",
                           rows=300, sample=f"fishing_{gubun}")
        except ApiError as e:
            print(f"⚠ 낚시지수({gubun})를 건너뜁니다: {e}")

    FIELD = json.loads(os.environ.get("FISHING_FIELDS", "{}") or "{}")
    f = {"name": "seafsPstnNm", "lat": "lat", "lon": "lot", "date": "predcYmd",
         "idx": "totalIndex", "fish": "seafsTgfshNm", "sea": "minWtem", "tide": "tdlvHrCn", **FIELD}
    points = []
    for it in items:
        try:
            points.append({
                "name": it.get(f["name"], ""), "lat": float(it[f["lat"]]), "lon": float(it[f["lon"]]),
                "date": str(it.get(f["date"], "")).replace("-", "")[:8],
                "idx": it.get(f["idx"], ""), "fish": it.get(f["fish"], ""),
                "sea": it.get(f["sea"]), "tide": it.get(f["tide"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    print(f"낚시지수 레코드 {len(points)}건")
    return points


def attach_fishing(camps, points):
    by_place = defaultdict(list)
    for p in points:
        by_place[(p["name"], p["lat"], p["lon"])].append(p)
    for c in camps:
        best, best_d = None, None
        for (name, lat, lon), recs in by_place.items():
            d = haversine(c["lat"], c["lon"], lat, lon)
            if best_d is None or d < best_d:
                best, best_d = (name, recs), d
        if best and best_d <= FISH_MAX_KM:
            name, recs = best
            days = defaultdict(list)
            for r in recs:
                days[r["date"]].append(r)
            c["point"] = {"name": name, "km": round(best_d, 1)}
            c["fishDays"] = {}
            for d, rs in days.items():
                top = max(rs, key=lambda r: FISH_LEVEL.get(r["idx"], 0))
                # 지수가 가장 좋은 어종 이름 (기타어종 제외, 최대 2개)
                fish = []
                for r in rs:
                    if r["idx"] == top["idx"] and r["fish"] and r["fish"] != "기타어종" and r["fish"] not in fish:
                        fish.append(r["fish"])
                c["fishDays"][d] = {"idx": top["idx"], "fish": "·".join(fish[:2]), "sea": top["sea"], "tide": top["tide"]}
        elif best:
            c["point"] = {"name": None, "km": round(best_d, 1)}


# ───────────────────────── 5. 점수 ─────────────────────────

def weather_score(w):
    return max(0, round(40 - w["rain"] * 0.3 - max(0, w["wind"] - 4) * 3))


def build(camps, grids, now):
    dates = sorted({d for g in grids.values() if g for d, v in g.items() if v})
    today = now.strftime("%Y%m%d")
    dates = [d for d in dates if d >= today][:4]
    out_sites = []
    for c in camps:
        g = grids.get(c.pop("grid"), None)
        if not g:
            continue
        days = {}
        for d in dates:
            w = g.get(d)
            if not w:
                continue
            day = dict(w)
            day["weather"] = weather_score(w)
            fd = (c.get("fishDays") or {}).get(d)
            if fd:
                day.update({"idx": fd["idx"], "fishName": fd["fish"], "sea": fd["sea"], "tide": fd["tide"]})
                day["fishScore"] = FISH_POINTS.get(FISH_LEVEL.get(fd["idx"], 0))
            days[d] = day
        if not days:
            continue
        c.pop("fishDays", None)
        c["days"] = days
        c.setdefault("near", [])
        out_sites.append(c)

    wd = "월화수목금토일"
    date_meta = [{"key": d, "label": f"{wd[datetime.strptime(d, '%Y%m%d').weekday()]} {int(d[4:6])}/{int(d[6:])}",
                  "weekend": datetime.strptime(d, "%Y%m%d").weekday() >= 5} for d in dates]
    zones = Counter(s["zone"] for s in out_sites)
    print("권역별:", dict(zones))
    return {
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "demo": False,
        "dates": date_meta,
        "hasFishing": any("point" in s and s["point"].get("name") for s in out_sites),
        "sites": out_sites,
    }


def main():
    now = datetime.now(KST)
    camps = fetch_camps()
    attach_pet_places(camps)
    attach_fishing(camps, fetch_fishing())
    grids = fetch_weather(camps, now)
    result = build(camps, grids, now)
    if not result["sites"]:
        sys.exit("결과가 비어 있어 기존 데이터를 유지합니다.")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"저장 완료: 캠핑장 {len(result['sites'])}곳, 날짜 {[d['label'] for d in result['dates']]}")


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        msg = str(e)
        hint = ""
        if "NOT_REGISTERED" in msg:
            hint = "\n→ 인증키가 아직 등록되지 않았거나 해당 API 활용신청이 안 된 상태입니다. 신청 후 1~2시간 뒤 다시 실행해 주세요."
        elif "EXCEEDS" in msg:
            hint = "\n→ 오늘 호출 한도를 넘었습니다. 내일 자동으로 다시 실행됩니다."
        sys.exit(f"API 오류: {msg}{hint}")
