# 주말 바다캠낚 — 프로젝트 안내 (Claude Code용)

이 파일은 claude.ai 대화에서 이어받은 프로젝트의 맥락입니다. 전체 대화 흐름은 `docs-handoff/CONVERSATION.md` 에 있습니다.

## 사용자
- 창현. 바이브코딩 방식(코딩 경험 거의 없음)이라 단계별로 쉽게 안내할 것.
- 한국어로 대화. 부업·수익화 목적의 웹앱.
- 공무원 신분이라 광고·제휴 수익이 생기면 겸직허가 확인이 필요하다고 안내한 상태.

## 앱 개요
전국 해안 캠핑장을 **날씨(40) + 바다낚시지수(40) + 반려견 동반/편의(20)** 로 점수 매겨 순위로 보여주는 웹앱.
- 권역: 서해 · 남해 · 동해 · 제주 → 시군 2단 필터. 반려견 동반 필터(켜면 불가 캠핑장 제외).
- 차별점: "반려견과 함께 바다 캠핑 + 낚시" 교집합. 각각의 단일 앱(캠핑 날씨, 펫캠핑, 물때)은 이미 있음.
- 15km 안에 낚시지수 포인트가 없으면 낚시 점수 제외, 날씨+편의 60점을 100점으로 환산.
- 출시 전략: 데이터는 전국, 공개는 남해안 권역부터 단계적으로(미결정, 사용자가 원하면 "오픈 예정" 표시 추가).

## 구조
```
scripts/collect.py    매일 실행되는 수집기 (표준 라이브러리만 사용)
scripts/demo_data.py  가짜 API 응답으로 collect.py 전 과정을 돌려 예시 데이터 생성
docs/index.html       GitHub Pages 웹페이지 (docs/data/sites.json 을 읽음)
.github/workflows/update.yml  매일 05:40, 17:40 KST 자동 실행
README.md             설정 방법(시크릿, Pages, 변수)
```
- 인증키: GitHub Secret `DATA_GO_KR_KEY` (공공데이터포털 일반 인증키 Decoding). 코드·결과물에 절대 넣지 말 것.
- 고캠핑 API는 하루 1,000건 제한 → 하루 1~2회 일괄 수집 구조.
- 기상청 예보는 캠핑장 좌표를 격자(nx, ny)로 바꿔 격자당 1회 호출.

## 사용 API (모두 공공데이터포털, 사용자가 활용신청 완료)
1. 한국관광공사_고캠핑 정보 조회서비스_GW — `B551011/GoCamping/basedList`, 해안 판별은 `lctCl`(해변·섬), 반려동물은 `animalCmgCl`
2. 한국관광공사_반려동물 동반여행 서비스 — `B551011/KorPetTourService2/areaBasedList2`
3. 기상청_단기예보 조회서비스 — `1360000/VilageFcstInfoService_2.0/getVilageFcst`
4. 국립해양조사원_바다낚시지수 조회 — `1192136/fcstFishingv2/GetFcstFishingApiServicev2` (포털 Swagger로 확인, 2026-10-04). 필수 `type=json`, `gubun=갯바위|선상`, numOfRows 최대 300, 7일 예측. 응답은 `response` 감싸기 없이 `header/body`가 최상위일 수 있어 call()에서 보정. 필드: seafsPstnNm, lat, lot, predcYmd, predcNoonSeCd(시간), totalIndex, lastScr, seafsTgfshNm, tdlvHrCn(물때), min/maxWtem 등.
- 게이트웨이 키 오류는 HTTP 403 + `OpenAPI_ServiceResponse` JSON으로 옴 → call()에서 코드 추출.

## 현재 상태 (2026-10-07)
- 프로젝트 위치: `C:\Users\USER\Desktop\부업프로젝트\badacamnak`. 저장소 https://github.com/kch4936-gif/badacamnak , 사이트 https://kch4936-gif.github.io/badacamnak/
- Secret·Pages·Actions 설정 완료. 첫 실제 실행 성공(약 10분): 해안 캠핑장 408곳(서해 184·남해 132·동해 78·제주 14), 반려견 가능 143곳, 15km 안 낚시 포인트 163곳.
- 첫 실행 후 수정: 저녁 실행 때 낮이 지나간 '오늘' 제외, 대상어에서 '기타어종' 제외.
- git: `C:\Program Files\Git\cmd\git.exe` (Claude 셸 PATH에 없음). 자격증명 저장돼 push 가능.

- 결정(2026-10-07): **전국 한 번에 공개**. 사용자 **겸직허가 확인 완료**. 서해·남해 경계(전남 해남·진도·영암)는 `zones` 로 두 권역 모두 표시. 반려견 표기 빈 곳은 동반 불가로 분류.

## 다음 할 일
1. 광고·수익화 붙이기(애드센스 등), 검색 노출(제목·설명·공유 미리보기).
