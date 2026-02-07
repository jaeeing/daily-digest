# Daily Trading Digest

AI 기반 글로벌 뉴스 분석 및 트레이딩 인사이트 자동 생성 시스템

## 📋 프로젝트 개요

Daily Trading Digest는 **Google Gemini AI**를 활용하여 글로벌 뉴스를 자동으로 수집·분석하고, 투자자를 위한 실시간 트레이딩 인사이트를 생성하는 시스템입니다.

### 핵심 기능

- 🌍 **실시간 글로벌 뉴스 수집**: GDELT API를 통한 최근 24시간 내 주요 뉴스 수집
- 🤖 **AI 기반 분석**: Google Gemini 2.5 Flash로 뉴스 → 투자 인사이트 자동 변환
- 📊 **프로필 기반 맞춤 분석**: 시나리오별 최적화된 키워드와 프롬프트 (default, fomc, earnings, china-policy, geopolitical)
- 📨 **자동 전송**: Slack/Email로 매일 아침 자동 리포트 전송
- 🎨 **HTML 이메일**: 표 스타일링, 클릭 가능한 링크, 모바일 반응형 디자인
- 🔗 **종목 링크 자동 생성**: 한국 종목(네이버 금융), 미국 종목(야후 파이낸스) 링크 자동 삽입
- ⚙️ **GitHub Actions 자동화**: 매일 07:30 KST 자동 실행

---

## 🎯 사용 시나리오

### Scenario 1: 일일 트레이딩 다이제스트 (Default)

**대상**: 주식 단타 트레이더, 데이 트레이더

**실행 시간**: 매일 07:30 KST (한국 장 개장 전)

**분석 내용**:
- 최근 24시간 글로벌 주요 뉴스 수집
- 정치/경제/기술 테마별 분류
- 관련 수혜주 및 리스크 종목 분석
- 매매 전략 제안 (시초가 매수/눌림목 매수/관망)

**키워드**:
```
inflation, nasdaq, semiconductor, artificial intelligence,
recession, earnings, dollar, china, geopolitical, employment
```

**프로필 설정**:
```bash
# 환경변수 없이 실행 (기본값)
python digest.py

# 또는 명시적으로
DIGEST_PROFILE=default python digest.py
```

---

### Scenario 2: FOMC 특별 리포트

**대상**: 금리 정책 관심 투자자

**실행 시**: FOMC 회의 기간 또는 주요 금리 이벤트 전후

**프로필 설정**:
```bash
DIGEST_PROFILE=fomc python digest.py
```

**특화 분석**:
- 연준(Fed) 관련 뉴스 집중 수집
- 금리, 인플레이션, 채권 시장 동향
- **시간 범위 확장 (36시간)** - 중요 이벤트 놓치지 않도록

**키워드**:
```
fomc, federal reserve, powell, interest rate, dot plot,
cpi, pce, inflation, treasury yield, dollar index
```

---

### Scenario 3: 실적 시즌 리포트

**대상**: 실적 발표 주시 투자자

**실행 시**: 분기별 실적 발표 시즌

**프로필 설정**:
```bash
DIGEST_PROFILE=earnings python digest.py
```

**특화 분석**:
- 글로벌 기업 실적 발표 모니터링
- 가이던스, 컨센서스 대비 서프라이즈 분석
- 국내 연관주 영향 분석
- **시간 범위 확장 (30시간)** - 장 마감 후 실적 발표 포함

**키워드**:
```
earnings, guidance, forecast, outlook, revenue,
operating margin, beat, miss, surprise, disclosure
```

---

### Scenario 4: 중국 정책 모니터링

**대상**: 중국 정책 영향 관심 투자자

**프로필 설정**:
```bash
DIGEST_PROFILE=china-policy python digest.py
```

**특화 분석**:
- 중국 정부 정책 변화
- 규제 리스크 및 기회
- 한국 기업에 미치는 영향

---

### Scenario 5: 지정학 리스크 모니터링

**대상**: 지정학 리스크 관심 투자자

**프로필 설정**:
```bash
DIGEST_PROFILE=geopolitical python digest.py
```

**특화 분석**:
- 국제 분쟁 및 긴장 상황
- 무역 분쟁, 제재
- 방산/에너지 섹터 영향

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions                           │
│               (매일 07:30 KST 자동 실행)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  digest.py (Main Script)                     │
├─────────────────────────────────────────────────────────────┤
│  1. 프로필 로드 (DIGEST_PROFILE 환경변수)                     │
│  2. 뉴스 수집 (GDELT API)                                     │
│  3. AI 분석 (Google Gemini)                                  │
│  4. HTML 변환 (Markdown → HTML with inline CSS)              │
│  5. 리포트 전송 (Slack/Email)                                │
└─────┬───────────────────────┬───────────────────────────┬───┘
      │                       │                           │
      ▼                       ▼                           ▼
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ GDELT API    │    │  Google Gemini   │    │  Slack/Email    │
│ (뉴스 수집)   │    │  AI (분석 생성)   │    │  (리포트 전송)   │
└──────────────┘    └──────────────────┘    └─────────────────┘
      │                       │                           │
      │                       │                           │
      ▼                       ▼                           ▼
 70개 뉴스 수집         AI 다이제스트 생성          자동 알림 전송
                      (Markdown 형식)           (HTML 이메일)
```

### 데이터 흐름

1. **프로필 로드** (load_runtime_config)
   - `DIGEST_PROFILE` 환경변수 읽기
   - 해당 프로필 JSON 파일 로드 (`config/profiles/{profile}.json`)
   - 설정 병합: 환경변수 > 프로필 설정 > 기본 설정

2. **뉴스 수집** (fetch_recent_news)
   - GDELT API에서 최근 N시간 뉴스 검색 (프로필별 시간 범위)
   - 키워드 + 테마 쿼리 조합
   - 최대 120개 수집 → 상위 70개 선별

3. **AI 분석** (generate_digest)
   - Google Gemini 2.5 Flash API 호출
   - RICE 프롬프트 기반 구조화된 분석
   - 마크다운 표 형식의 투자 인사이트 생성
   - 종목 링크 자동 삽입 (한국: 네이버 금융, 미국: 야후 파이낸스)

4. **HTML 변환** (send_email)
   - 마크다운 → HTML 변환 (표, 링크, 스타일)
   - CSS → 인라인 스타일 변환 (premailer) - 이메일 클라이언트 호환성
   - 모바일 반응형 디자인 적용

5. **리포트 전송** (send_to_slack / send_email)
   - Slack: 3500자 단위 청크 분할 전송
   - Email: HTML 이메일 전송 (SMTP)
   - 종목 링크 클릭 시 해당 금융 사이트로 이동

6. **모니터링** (write_run_report)
   - JSON/Markdown 리포트 생성 (artifacts/)
   - GitHub Actions 요약에 자동 추가

---

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/jaeeing/daily-digest.git
cd daily-digest

# Python 패키지 설치
pip install -r requirements.txt
```

**필수 패키지**:
- `google-genai>=1.0.0` - Google Gemini API (구 google-generativeai 대체)
- `requests>=2.32.0` - HTTP 요청
- `python-dateutil>=2.9.0` - 날짜 처리
- `markdown>=3.5.0` - 마크다운 → HTML 변환
- `premailer>=3.10.0` - CSS → 인라인 스타일 변환 (이메일 호환성)

### 2. API 키 발급

#### Google Gemini API (필수)
1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. API 키 생성 (무료 tier: 일일 1,500 요청)
3. 환경변수 설정:
   ```bash
   export GOOGLE_API_KEY="your-api-key-here"
   ```

#### Slack Webhook (선택)
1. Slack 워크스페이스에서 Incoming Webhook 생성
2. 환경변수 설정:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
   ```

#### SMTP 이메일 설정 (선택)

##### 네이버 메일 사용 (권장)
```bash
export SMTP_HOST="smtp.naver.com"
export SMTP_PORT="587"
export SMTP_USER="your-id@naver.com"
export SMTP_PASS="your-password"  # 2단계 인증 시 앱 비밀번호
export MAIL_FROM="your-id@naver.com"
export MAIL_TO="recipient@naver.com"
```

**네이버 메일 설정 방법**:
1. 네이버 메일 → 환경설정 → POP3/IMAP 설정
2. IMAP/SMTP 사용 "사용함" 선택
3. 2단계 인증 사용 시: 앱 비밀번호 생성

##### Gmail 사용
```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASS="your-app-password"  # 앱 비밀번호 생성 필요
export MAIL_FROM="your-email@gmail.com"
export MAIL_TO="recipient@gmail.com"
```

**Gmail 앱 비밀번호 생성**:
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성 → "메일" 선택
3. 생성된 16자리 비밀번호 사용

### 3. 로컬 실행

#### 기본 프로필 실행
```bash
# 방법 1: 환경변수 한 줄로 설정
GOOGLE_API_KEY="your-key" python digest.py

# 방법 2: export 후 실행
export GOOGLE_API_KEY="your-key"
python digest.py
```

#### 특정 프로필 실행
```bash
# FOMC 리포트 (36시간 뉴스, 금리 중심)
DIGEST_PROFILE=fomc python digest.py

# 실적 시즌 리포트 (30시간 뉴스, 실적 중심)
DIGEST_PROFILE=earnings python digest.py

# 중국 정책 리포트
DIGEST_PROFILE=china-policy python digest.py

# 지정학 리스크 리포트
DIGEST_PROFILE=geopolitical python digest.py
```

#### 설정 커스터마이징 (환경변수 오버라이드)
```bash
# 시간 범위 변경 (프로필 설정보다 우선)
TIME_WINDOW_HOURS=48 DIGEST_PROFILE=fomc python digest.py

# 모델 변경 (기본: gemini-2.5-flash)
GEMINI_MODEL=gemini-1.5-pro python digest.py

# 수집 뉴스 개수 변경
MAX_NEWS_IN_CONTEXT=100 python digest.py
```

#### 이메일 포함 전체 실행 예시
```bash
GOOGLE_API_KEY="your-key" \
SMTP_HOST="smtp.naver.com" \
SMTP_PORT="587" \
SMTP_USER="your-id@naver.com" \
SMTP_PASS="your-password" \
MAIL_FROM="your-id@naver.com" \
MAIL_TO="recipient@naver.com" \
DIGEST_PROFILE=fomc \
python digest.py
```

### 4. GitHub Actions 설정

#### Repository Secrets 추가
`Settings → Secrets and variables → Actions → Secrets` 탭에서:

```
GOOGLE_API_KEY: your-google-api-key (필수)
GEMINI_MODEL: gemini-2.5-flash (선택, 기본값)
SLACK_WEBHOOK_URL: your-slack-webhook (선택)
SMTP_HOST: smtp.naver.com (선택, 이메일 사용 시)
SMTP_PORT: 587 (선택, 이메일 사용 시)
SMTP_USER: your-id@naver.com (선택)
SMTP_PASS: your-password (선택)
MAIL_FROM: your-id@naver.com (선택)
MAIL_TO: recipient@naver.com (선택)
```

#### Repository Variables 추가 (선택)
`Settings → Secrets and variables → Actions → Variables` 탭에서:

```
DIGEST_PROFILE: default (또는 fomc, earnings, china-policy, geopolitical)
```

**변경 방법**:
- 평소: `DIGEST_PROFILE = default` (일반 뉴스)
- FOMC 주간: `DIGEST_PROFILE = fomc` (금리 중심)
- 실적 시즌: `DIGEST_PROFILE = earnings` (실적 중심)

#### 수동 실행
1. Repository → `Actions` 탭 이동
2. "Daily Trading Digest" 워크플로우 선택
3. `Run workflow` 클릭
4. 프로필 선택 가능 (Variables에 설정된 값 사용)

#### 스케줄 변경
`.github/workflows/daily-digest.yml` 파일 수정:
```yaml
on:
  schedule:
    - cron: '30 22 * * *'  # 07:30 KST (UTC+9)
    # 분 시 일 월 요일
    # 예: '0 14 * * *' = 매일 23:00 KST
```

**크론 표현식 예시**:
- `'30 22 * * *'` - 매일 07:30 KST (기본값)
- `'0 23 * * 1-5'` - 평일만 08:00 KST
- `'0 14,23 * * *'` - 매일 23:00, 08:00 KST (2회)

---

## 📂 프로젝트 구조

```
Daily-Digest/
├── digest.py                    # 메인 스크립트 (600+ lines)
├── requirements.txt             # Python 의존성
├── README.md                    # 프로젝트 문서
├── config/
│   ├── settings.json           # 전역 설정 (기본값)
│   ├── keywords.json           # 기본 키워드 목록
│   ├── prompts/
│   │   └── digest_rice.md      # AI 프롬프트 (RICE 포맷)
│   └── profiles/               # 시나리오별 프로필
│       ├── default.json        # 일반 트레이딩 (24h)
│       ├── fomc.json           # FOMC/금리 특화 (36h)
│       ├── earnings.json       # 실적 시즌 특화 (30h)
│       ├── china-policy.json   # 중국 정책 특화
│       └── geopolitical.json   # 지정학 리스크 특화
├── artifacts/                  # 실행 리포트 저장 (자동 생성)
│   ├── delivery-report-*.json # 실행 결과 JSON
│   └── delivery-report-*.md   # 실행 결과 마크다운
├── .github/
│   └── workflows/
│       └── daily-digest.yml    # GitHub Actions 워크플로우
└── test-*.py                   # 테스트 스크립트 (로컬 테스트용)
```

---

## ⚙️ 설정 파일 상세

### 프로필 시스템 동작 원리

프로필은 **읽기 전용**으로 동작하며, 실행 시 메모리에서만 병합됩니다:

```
설정 우선순위 (높음 → 낮음):
1. 환경변수 (TIME_WINDOW_HOURS=48)
2. 프로필 설정 (config/profiles/fomc.json)
3. 기본 설정 (config/settings.json)
4. 코드 내 기본값
```

**예시**:
```bash
# fomc.json의 time_window_hours=36 사용
DIGEST_PROFILE=fomc python digest.py

# 환경변수가 프로필 설정을 덮어씀 (48시간)
DIGEST_PROFILE=fomc TIME_WINDOW_HOURS=48 python digest.py
```

### config/settings.json (전역 기본 설정)
```json
{
  "time_window_hours": 24,        // 뉴스 수집 시간 범위 (시간)
  "max_gdelt_records": 120,       // GDELT API 최대 검색 개수
  "max_news_in_context": 70,      // AI에 전달할 뉴스 개수
  "slack_chunk_size": 3500,       // Slack 메시지 분할 크기
  "theme_query": "(economy OR market OR policy)"  // GDELT 테마 필터
}
```

### config/keywords.json (기본 키워드)
```json
{
  "keywords": [
    "inflation",              // 인플레이션
    "nasdaq",                 // 나스닥
    "semiconductor",          // 반도체
    "artificial intelligence",// AI
    "recession",              // 경기침체
    "earnings",               // 실적
    "dollar",                 // 달러
    "china",                  // 중국
    "geopolitical",           // 지정학
    "employment"              // 고용
  ]
}
```

**주의사항**:
- ⚠️ **한글 키워드 사용 불가** (GDELT API가 ASCII만 지원)
- 각 키워드 최소 3자 이상
- 키워드 개수 10개 이하 권장 (쿼리 길이 제한)

### config/profiles/fomc.json (FOMC 특화 프로필)
```json
{
  "settings": {
    "time_window_hours": 36,     // 36시간 수집 (기본 24h 대신)
    "max_gdelt_records": 180,    // 더 많은 기사 수집
    "max_news_in_context": 90,   // AI에 더 많은 컨텍스트 제공
    "theme_query": "(federal reserve OR fomc OR interest rate OR inflation)"
  },
  "keywords": [
    "fomc",
    "federal reserve",
    "powell",
    "interest rate",
    "dot plot",
    "cpi",
    "pce",
    "inflation",
    "treasury yield",
    "dollar index"
  ],
  "prompt_file": "prompts/digest_rice.md"  // 프롬프트 파일 지정
}
```

### config/profiles/custom.json (커스텀 프로필 만들기)

새로운 시나리오를 위한 프로필 생성:

```json
{
  "settings": {
    "time_window_hours": 48,              // 2일치 뉴스
    "max_gdelt_records": 200,
    "theme_query": "(technology OR innovation OR startup)"
  },
  "keywords": [
    "5g",
    "quantum computing",
    "blockchain",
    "venture capital",
    "ipo"
  ],
  "prompt_file": "prompts/digest_rice.md"
}
```

**사용법**:
```bash
DIGEST_PROFILE=custom python digest.py
```

---

## 🎨 프롬프트 커스터마이징

### RICE 프롬프트 구조

프롬프트는 `config/prompts/digest_rice.md`에서 수정 가능합니다:

```markdown
### R (Role) - 역할
당신은 10년 경력의 단기 트레이딩 전문가입니다.

### I (Instruction) - 지시사항
오늘 주식장 시작 전, 단타 매매에 활용할 수 있는 핵심 정보를 분석해주세요.

**필수 규칙:**
1. 모든 뉴스 제목은 한국어로 번역
2. 뉴스 출처와 게시일 명시
3. 종목 코드 링크 규칙:
   - 한국 종목: <a href="https://finance.naver.com/item/main.naver?code=005930">삼성전자 (005930)</a>
   - 미국 종목: <a href="https://finance.yahoo.com/quote/NVDA/">엔비디아 (NVDA)</a>

### C (Context) - 맥락
- 장 시작 전 30분~1시간 내 빠른 의사결정 필요
- 단타 매매 (당일~2-3일 보유) 관점

### E (Example) - 출력 형식
[표 형식의 구조화된 출력 예시]
```

### 중요 프롬프트 규칙

#### 1. 뉴스 출처 링크
```markdown
<div class="news-meta">
<strong>📰 출처</strong>: <a href="https://reuters.com/...">Reuters</a> | <strong>📅 게시일</strong>: 2026-02-07 14:30
</div>
```

#### 2. 종목 링크 자동 생성
AI가 다음 형식으로 종목을 출력하도록 프롬프트에 명시:

**한국 종목** (네이버 금융):
```html
<a href="https://finance.naver.com/item/main.naver?code=005930">삼성전자 (005930)</a>
```

**미국 종목** (야후 파이낸스):
```html
<a href="https://finance.yahoo.com/quote/NVDA/">엔비디아 (NVDA)</a>
```

#### 3. 표 형식 (마크다운)
```markdown
| 항목     | 내용                   |
| ------ | -------------------- |
| 뉴스 요약  | [1-2줄 요약]            |
| 수혜 종목  | <a href="...">삼성전자 (005930)</a>, <a href="...">엔비디아 (NVDA)</a> |
| 연결 고리  | [왜 이 뉴스가 이 종목에 영향?]  |
```

**주의**: 종목 링크에 백틱(`) 사용 금지 (HTML로 인식되지 않음)

---

## 📧 이메일 스타일링

### HTML 변환 프로세스

```python
# 1. Markdown → HTML
html_content = markdown.markdown(text, extensions=['tables', 'nl2br'])

# 2. CSS 스타일 추가
html_with_style = f"""
<style>
  table {{ border: 2px solid #2c3e50; }}
  th {{ background: #2c3e50; color: white; }}
  a {{ color: #3498db; font-weight: 600; }}
</style>
{html_content}
"""

# 3. 인라인 스타일로 변환 (이메일 호환성)
html_inlined = transform(html_with_style)  # premailer
```

### 이메일 클라이언트 호환성

**문제**: 대부분의 이메일 클라이언트는 `<style>` 태그를 보안상 차단합니다.

**해결**: `premailer` 라이브러리로 CSS를 인라인 스타일로 변환

```html
<!-- 변환 전 (차단됨) -->
<style>
  table { border: 2px solid #2c3e50; }
</style>
<table>...</table>

<!-- 변환 후 (정상 작동) -->
<table style="border: 2px solid #2c3e50;">...</table>
```

### 주요 스타일링 요소

- **표 헤더**: 진한 회색 그라데이션, 흰색 글자
- **첫 번째 열**: 연한 회색 배경 (항목명)
- **교차 행**: 흰색/연한 회색 번갈아 표시
- **링크**: 파란색, 호버 시 밑줄
- **반응형**: 모바일 화면 대응 (@media query)

---

## 📊 출력 예시

### 일일 다이제스트 리포트 (실제 출력)

```markdown
## 오늘의 핵심 뉴스 & 수혜주

---

### 1순위: 어도비-코그니전트 AI 협력, 주가 및 가치 상승 잠재력 시험대

<div class="news-meta">
<strong>📰 출처</strong>: <a href="https://finance.yahoo.com/news/adobe-cognizant-ai-deal-tests-150632209.html">Yahoo Finance</a> | <strong>📅 게시일</strong>: 2026-02-07 15:30
</div>

| 항목     | 내용                   |
| ------ | -------------------- |
| 뉴스 요약  | 어도비와 코그니전트가 AI 분야에서 협력. AI 기술 융합을 통한 신규 서비스 및 시장 확대 기대. |
| 수혜 종목  | <a href="https://finance.yahoo.com/quote/ADBE/">어도비 (ADBE)</a>, <a href="https://finance.yahoo.com/quote/CTSH/">코그니전트 (CTSH)</a> |
| 연결 고리  | 어도비의 크리에이티브 솔루션과 코그니전트의 컨설팅 서비스를 AI로 통합하여 시너지 창출 가능성. |
| 현재가/등락 | 확인 필요              |
| 예상 영향  | 상승, 강도(중)         |
| 매매 전략  | 시초가 매수 / 눌림목 매수 |
| 목표가    | 불확실                 |
| 손절가    | 불확실                 |

---

## 테마별 정리

| 테마       | 관련 뉴스 | 핵심 종목 | 강도  |
| -------- | ----- | ----- | --- |
| 글로벌 AI 테마 | 어도비-코그니전트 AI 협력, 애플 AI 칩 루머 | <a href="https://finance.yahoo.com/quote/ADBE/">어도비 (ADBE)</a>, <a href="https://finance.yahoo.com/quote/AAPL/">애플 (AAPL)</a> | *** |
| 실적 서프라이즈 | 톰슨 로이터 실적 예상치 상회 | <a href="https://finance.yahoo.com/quote/TRI/">톰슨 로이터 (TRI)</a> | **  |

---

## 오늘의 단타 전략 요약

1. **최우선 관심**: <a href="https://finance.yahoo.com/quote/AAPL/">애플 (AAPL)</a> 및 AI 반도체 관련주 - 애플 인텔리전스 루머
2. **차선 관심**: <a href="https://finance.yahoo.com/quote/ADBE/">어도비 (ADBE)</a> - AI 협력 시너지
3. **시장 분위기**: 강세 (특히 AI 및 대형 기술주 중심)
4. **주의사항**: AI 테마 강세 속 뉴스가 '루머'인 경우 변동성 주의, 손절 라인 명확히 설정
```

### 이메일에서 보이는 모습

- ✅ 표가 색상과 테두리로 잘 구분됨
- ✅ **출처 클릭** → 뉴스 원문으로 이동
- ✅ **종목명 클릭** → 네이버 금융/야후 파이낸스로 이동
- ✅ 모바일에서도 읽기 편한 반응형 레이아웃

---

## 🐛 트러블슈팅

### 1. GDELT API 오류

#### 문제: "Your query was too short or too long"
```
GDELT API Error: Your query was too short or too long
```

**원인**:
- 한글 키워드 사용 (GDELT는 ASCII만 지원)
- 키워드가 너무 짧음 (3자 미만)
- 쿼리 전체 길이가 너무 김 (키워드 + theme_query)

**해결**:
```json
// config/keywords.json
{
  "keywords": [
    // ❌ "금리" - 한글 불가
    // ❌ "ai" - 너무 짧음
    "inflation",              // ✅ 영문 3자 이상
    "nasdaq",
    "semiconductor"
    // ... 최대 10개 권장
  ]
}

// config/settings.json
{
  // ❌ theme_query: "(politics OR economy OR market OR policy OR earnings OR ...)"
  "theme_query": "(economy OR market OR policy)"  // ✅ 간결하게
}
```

**자동 필터링**:
```python
# digest.py에서 자동으로 한글 키워드 제거
english_keywords = [kw for kw in keywords if kw.isascii() and len(kw) >= 3]
```

### 2. Gemini API 오류

#### 문제: "Rate limit exceeded"
```
google.genai.errors.RateLimitError: 429 Resource has been exhausted
```

**원인**: 무료 tier 제한 초과
- 분당 15 요청
- 일일 1,500 요청
- 월 1,500 요청

**해결**:
1. GitHub Actions 실행 빈도 줄이기 (1일 1회 권장)
2. 로컬 테스트 횟수 제한
3. 유료 플랜 고려 (필요 시)

```yaml
# .github/workflows/daily-digest.yml
on:
  schedule:
    - cron: '30 22 * * *'  # 하루에 1회만 실행
```

### 3. 이메일 스타일이 적용되지 않음

#### 문제: 이메일에서 표가 스타일 없이 평범하게 보임

**원인**: 이메일 클라이언트가 `<style>` 태그 차단

**해결**: `premailer` 설치 확인
```bash
pip install premailer>=3.10.0
```

```python
# digest.py에서 자동 변환
from premailer import transform

html_inlined = transform(html_body)  # CSS → inline style
```

### 4. SMTP 전송 실패

#### 문제: "Connection unexpectedly closed"

**원인**: SMTP 설정 오류

**해결 (네이버 메일)**:
```bash
# ❌ 포트 465 (SSL) - 작동 안 할 수 있음
# ✅ 포트 587 (TLS) 사용
export SMTP_HOST="smtp.naver.com"
export SMTP_PORT="587"  # 587 사용!
```

```python
# digest.py (자동 처리됨)
server.starttls()  # TLS 시작
server.login(user, password)
```

#### 문제: "Authentication failed"

**해결**:
1. 네이버: 2단계 인증 사용 시 앱 비밀번호 생성
2. Gmail: 앱 비밀번호 필수 (일반 비밀번호 사용 불가)

### 5. 표 내용이 비어 있음

#### 문제: 이메일에 표 헤더만 보이고 내용이 없음
```
| 항목 | 내용
```

**원인**: AI가 표를 완성하지 못함 (프롬프트 문제)

**해결**: 프롬프트에서 백틱(`) 제거
```markdown
<!-- ❌ 백틱 사용 (HTML이 코드로 인식됨) -->
| 수혜 종목 | `<a href="...">삼성전자</a>` |

<!-- ✅ 백틱 없이 -->
| 수혜 종목 | <a href="...">삼성전자</a> |
```

### 6. 한글 종목 코드를 찾을 수 없음

**문제**: AI가 한국 종목 코드를 모름

**해결**: 프롬프트에 예시 명시
```markdown
3. **종목 코드 링크 규칙**:
   - 한국 종목: 삼성전자는 005930, SK하이닉스는 000660
   - 예시: <a href="https://finance.naver.com/item/main.naver?code=005930">삼성전자 (005930)</a>
```

또는 AI에게 "종목 코드를 모르면 종목명만 출력" 지시

---

## 📈 성능 최적화

### API 비용 절감

| 항목                   | 무료 Tier    | 최적화 방법                  |
|------------------------|--------------|------------------------------|
| Gemini API 요청        | 1,500/day    | 1일 1회 실행 권장             |
| GDELT API 요청         | 무제한       | 캐싱 불필요                  |
| Slack 메시지 전송      | 무제한       | 3500자 단위 분할 전송         |
| SMTP 이메일 전송       | 무제한       | 네이버/Gmail 무료 사용 가능   |

### 응답 속도 개선

**현재 실행 시간**: 약 30~40초
- GDELT API: ~2초
- Gemini API: ~30초 (가장 오래 걸림)
- 이메일 전송: ~2초

**최적화 방안**:
```python
# 1. 모델 변경 (속도 vs 품질 트레이드오프)
GEMINI_MODEL=gemini-2.0-flash  # 더 빠름 (품질 약간 하락)

# 2. 뉴스 개수 줄이기
MAX_NEWS_IN_CONTEXT=50  # 기본 70개 → 50개

# 3. 병렬 처리 (고급)
import concurrent.futures

def fetch_and_analyze_parallel():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_news = executor.submit(fetch_recent_news, cfg)
        future_profile = executor.submit(load_profile, profile_name)
        news = future_news.result()
        profile = future_profile.result()
```

---

## 🔧 고급 사용법

### 1. 멀티 프로필 동시 실행

여러 시나리오를 동시에 분석하고 싶을 때:

**.github/workflows/multi-digest.yml**:
```yaml
name: Multi Profile Digest

on:
  schedule:
    - cron: '30 22 * * *'

jobs:
  default-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python digest.py
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          DIGEST_PROFILE: default
          MAIL_TO: default@example.com

  fomc-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: python digest.py
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          DIGEST_PROFILE: fomc
          MAIL_TO: fomc@example.com
```

### 2. 커스텀 알림 채널 추가

Discord, Telegram 등 다른 서비스 연동:

```python
# digest.py에 추가
def send_to_discord(text: str) -> DeliveryStatus:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return DeliveryStatus(enabled=False, ...)

    payload = {"content": text}
    resp = requests.post(webhook, json=payload, timeout=10)
    resp.raise_for_status()

    return DeliveryStatus(enabled=True, attempted=True, success=True, detail="discord")
```

### 3. 데이터베이스 저장 (히스토리 관리)

```python
# digest_db.py (새 파일)
import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('digests.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT,
            content TEXT,
            news_count INTEGER,
            created_at TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def save_digest(profile: str, content: str, news_count: int):
    conn = init_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO digests (profile, content, news_count, created_at) VALUES (?, ?, ?, ?)",
        (profile, content, news_count, datetime.now())
    )
    conn.commit()
    conn.close()

# digest.py의 main() 함수에 추가
save_digest(cfg.profile, digest, len(news_items))
```

### 4. 웹 대시보드 (Flask)

```python
# dashboard.py
from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

@app.route('/')
def index():
    conn = sqlite3.connect('digests.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM digests ORDER BY created_at DESC LIMIT 10")
    digests = cursor.fetchall()
    conn.close()
    return render_template('index.html', digests=digests)

if __name__ == '__main__':
    app.run(debug=True)
```

---

## 🤝 기여 방법

1. Fork the repository
2. Create your feature branch
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. Commit your changes
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. Push to the branch
   ```bash
   git push origin feature/amazing-feature
   ```
5. Open a Pull Request

### 기여 가이드라인

- 코드 스타일: PEP 8 준수
- 타입 힌트 사용 권장
- 주요 함수에 docstring 추가
- 테스트 코드 작성 (가능하면)

---

## 📝 변경 이력

### v2.0.0 (2026-02-08)
- ✨ HTML 이메일 지원 (마크다운 → HTML 변환)
- ✨ 인라인 CSS 스타일링 (premailer 통합)
- ✨ 클릭 가능한 뉴스 출처 링크
- ✨ 종목 코드 자동 링크 (네이버 금융, 야후 파이낸스)
- 🐛 백틱으로 감싼 링크 문제 수정
- 🐛 이메일 클라이언트 CSS 차단 문제 해결

### v1.5.0 (2026-02-07)
- 🔄 OpenAI API → Google Gemini API 마이그레이션
- ✨ 프로필 시스템 추가 (default, fomc, earnings, china-policy, geopolitical)
- ✨ 네이버 SMTP 지원
- 🐛 GDELT API 한글 키워드 문제 해결
- 🐛 SMTP TLS 연결 문제 해결

### v1.0.0 (Initial Release)
- ✨ GDELT API 뉴스 수집
- ✨ OpenAI GPT 분석
- ✨ Slack 알림
- ✨ GitHub Actions 자동화

---

## 📜 라이선스

이 프로젝트는 개인 사용 목적으로 제작되었습니다.

---

## 🙏 참고 자료

### API 문서
- [Google Gemini API](https://ai.google.dev/docs) - AI 분석 엔진
- [GDELT API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) - 글로벌 뉴스 데이터
- [GitHub Actions](https://docs.github.com/en/actions) - 자동화 워크플로우

### 라이브러리
- [google-genai](https://pypi.org/project/google-genai/) - Google Gemini Python SDK
- [premailer](https://pypi.org/project/premailer/) - CSS to inline styles
- [markdown](https://pypi.org/project/Markdown/) - Markdown to HTML

### 금융 정보
- [네이버 금융](https://finance.naver.com/) - 한국 주식 시세
- [야후 파이낸스](https://finance.yahoo.com/) - 미국 주식 시세

---

## 📧 연락처

문의사항이나 버그 리포트는 GitHub Issues에 등록해주세요.

**Repository**: [https://github.com/jaeeing/daily-digest](https://github.com/jaeeing/daily-digest)

**Made with ❤️ by Claude Sonnet 4.5**
