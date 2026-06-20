# 물가나우 (MulgaNow) — MVP

사업계획서에 정의된 핵심 기능(① 실시간 가격비교 ② 물가지수성 변동 추이)을 구현한
**로컬 실행용 풀스택 MVP**입니다.

- 백엔드: Python Flask (`backend/`)
- 프론트엔드: 순수 HTML/CSS/JS + Chart.js (`frontend/`)
- 데이터 소스: **KAMIS(농산물유통정보) Open API** (실시간성이 가장 좋아 1차 연동 대상으로 선정)

---

## 1. 사전 준비: API 키 발급

1. https://www.kamis.or.kr 회원가입
2. https://www.kamis.or.kr/customer/reference/openapi_write.do 에서 Open API 신청
3. 발급받은 **인증키(Cert Key)** 와 **계정 아이디(Cert ID)** 를 확인

> ⚠️ KAMIS는 회원가입 시 즉시 키가 발급되며, 일부 액션은 별도 승인이 필요할 수 있습니다.
> 정확한 파라미터 스펙은 항상 공식 문서를 함께 참고하세요:
> https://www.kamis.or.kr/customer/reference/openapi_list.do

---

## 2. 설치 및 실행

```bash
cd backend
pip install -r requirements.txt

# .env.example을 복사해서 실제 키 입력
cp .env.example .env
# .env 파일을 열어 KAMIS_CERT_KEY, KAMIS_CERT_ID 값을 채워주세요

python app.py
```

브라우저에서 **http://localhost:5000** 접속.

---

## 3. 폴더 구조

```
mulganow/
├── backend/
│   ├── app.py              # Flask 서버 + API 엔드포인트
│   ├── kamis_client.py     # KAMIS Open API 호출 모듈
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

---

## 4. 제공 기능 (사업계획서 매핑)

| 사업계획서 기능 | 구현 위치 | 설명 |
|---|---|---|
| 4.1 실시간 가격비교 | `/api/today-prices` + 메인 그리드 | KAMIS 최근일자 가격을 카드 형태로 표시, 품목 검색 가능 |
| 4.2 물가지수 흐름 | `today_price`의 전월대비(%) 뱃지 | KAMIS 응답에 포함된 1개월전/1년전 가격으로 변동률 계산 |
| 4.1 가격 추이 차트 | `/api/trend` + 모달 내 라인 차트 | 품목 클릭 시 최근 14/30/90일 가격 추이 표시 |

> 💡 KAMIS의 `dailySalesList` 응답에는 당일/1일전/1개월전/1년전 가격이 함께 내려오기 때문에,
> 별도로 통계청 KOSIS 물가지수 API를 연동하지 않고도 "체감 물가 변동"을 보여줄 수 있도록 설계했습니다.

---

## 5. API 엔드포인트

### `GET /api/today-prices`
| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `cls` | `01`=소매, `02`=도매 | `02` |
| `q` | 품목명 검색 키워드 | (없음, 전체) |

### `GET /api/trend`
| 파라미터 | 설명 | 필수 |
|---|---|---|
| `category` | KAMIS 품목분류코드 | ✅ |
| `item` | KAMIS 품목코드 | ✅ |
| `kind` | 품종코드 (기본 `00`) | - |
| `rank` | 등급코드 (기본 `04`) | - |
| `days` | 조회기간(일), 기본 30 | - |
| `cls` | `01`/`02` | - |

---

## 6. 알아두어야 할 점 (중요)

- **KAMIS 파라미터명/코드값은 운영기관 정책에 따라 변경될 수 있습니다.** 이 코드는 공식 문서와
  공개된 예제를 바탕으로 작성했지만, 실제 응답이 예상과 다르면(`raw` 필드를 콘솔에 출력해)
  필드명을 맞춰 `app.py`의 `_extract_items` / `_normalize_item` / `_extract_trend_points`
  함수를 조정해주세요.
- 카드 클릭 시 추이 차트가 비어 있다면, 해당 품목의 `category_code`/`item_code` 매핑이
  KAMIS 코드표와 다를 수 있다는 의미입니다. KAMIS 품목코드표(공식 다운로드 파일)를 참고해
  `kind_code`, `product_rank_code`를 품목별로 맞춰주는 것을 권장합니다.
- 현재는 **단일 사용자 로컬 실행**을 가정한 MVP입니다. 운영 배포 시에는:
  - API 키를 서버 환경변수로만 관리 (프론트엔드에 노출 금지 — 이미 이 구조는 안전합니다)
  - 캐싱(예: 1일 1회 갱신) 추가 — KAMIS는 일별 갱신이므로 매 요청마다 호출할 필요 없음
  - Rate limit 대응 로직 추가

---

## 7. 다음 확장 단계 (사업계획서 8장 운영계획 참고)

1. **한국소비자원 참가격(price.go.kr)** 연동 — 유통업체별 비교 기능 추가
2. **통계청 KOSIS Open API** 연동 — 전국 단위 소비자물가지수(CPI) 대시보드 추가
3. 사용자 계정 + "내 장바구니" 등록 기능 (현재는 비로그인 전체 품목 조회만 지원)
4. 가격 변동 알림(이메일/푸시)
