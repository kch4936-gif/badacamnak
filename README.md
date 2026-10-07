# 주말 바다캠낚

전국 해안 캠핑장을 **날씨 · 바다낚시지수 · 반려견 동반 조건**으로 점수 매겨 보여주는 웹앱입니다.
공공데이터포털 무료 API 4종을 매일 자동으로 모아 계산합니다.

## 동작 방식

```
GitHub Actions (매일 05:40, 17:40)
  └ scripts/collect.py
      ├ 고캠핑 API ─────────── 입지가 '해변'·'섬'인 캠핑장만 선별
      ├ 반려동물 동반여행 API ─ 캠핑장 반경 10km 동반 장소 3곳
      ├ 기상청 단기예보 API ── 예보 격자당 1회 호출, 낮 시간 강수·풍속·파고 요약
      └ 바다낚시지수 API ───── 15km 안 포인트 지수 (설정 시)
  └ docs/data/sites.json 저장 → GitHub Pages(docs/index.html)가 읽어서 표시
```

인증키는 GitHub Secrets 에만 저장되고 코드·결과 파일·웹페이지 어디에도 남지 않습니다.

## 처음 설정 (한 번만)

1. **인증키 넣기**: 저장소 `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `DATA_GO_KR_KEY`
   - Secret: 공공데이터포털 마이페이지의 **일반 인증키(Decoding)** 값
2. **웹사이트 켜기**: `Settings → Pages → Build and deployment`
   - Source: `Deploy from a branch` / Branch: `main`, 폴더 `/docs` → Save
3. **첫 실행**: `Actions → 데이터 업데이트 → Run workflow`
   - 초록색 체크가 뜨면 성공. 빨간색이면 로그 맨 아래 'API 오류' 문구를 확인하세요.

## 바다낚시지수

기본으로 연결돼 있습니다 (`1192136/fcstFishingv2/GetFcstFishingApiServicev2`, 갯바위·선상 둘 다 수집).
따로 설정할 것은 없고, 바꾸고 싶을 때만 `Settings → Secrets and variables → Actions → Variables` 에 추가합니다.

| 이름 | 내용 |
|---|---|
| `FISHING_URL` | 다른 주소를 쓸 때. `off` 로 두면 낚시 점수 없이 계산 |
| `FISHING_PARAMS` | 추가 요청변수 JSON. 예: `{"reqDate":"20261010"}` |
| `FISHING_FIELDS` | 응답 필드 이름이 바뀌었을 때만. 예: `{"lon":"lot"}` |

실행 후 `samples/fishing_갯바위.json`, `samples/fishing_선상.json` 에 실제 응답 앞부분이 저장됩니다.

## 자주 나는 오류

| 메시지 | 의미 |
|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` | 키 등록 대기 중(신청 후 1~2시간) 또는 해당 API 미신청 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` | 하루 호출 한도 초과. 다음 날 자동 재실행 |
| `결과가 비어 있어 기존 데이터를 유지합니다` | 수집 실패 시 기존 화면을 그대로 둡니다 |

## 로컬에서 예시 데이터로 확인

```bash
python scripts/demo_data.py        # 가짜 응답으로 전체 처리 과정을 돌려 docs/data/sites.json 생성
python -m http.server -d docs 8000 # http://localhost:8000
```

## 데이터 출처

한국관광공사 고캠핑 정보 · 한국관광공사 반려동물 동반여행 서비스 · 국립해양조사원 바다낚시지수 · 기상청 단기예보 (공공데이터포털, 공공누리 출처표시)
