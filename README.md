# Daily Trading Digest

AI 기반 글로벌 뉴스 분석 및 트레이딩 인사이트 자동 생성 시스템

## 📋 프로젝트 개요

Daily Trading Digest는 **Google Gemini AI**를 활용하여 글로벌 뉴스를 자동으로 수집·분석하고, 투자자를 위한 실시간 트레이딩 인사이트를 생성하는 시스템입니다.

### 핵심 기능

- 🌍 **실시간 글로벌 뉴스 수집**: GDELT API를 통한 최근 24시간 내 주요 뉴스 수집
- 🤖 **AI 기반 분석**: Google Gemini 2.5 Flash로 뉴스 → 투자 인사이트 자동 변환
- 📊 **프로필 기반 맞춤 분석**: 시나리오별 최적화된 키워드와 프롬프트
- 📨 **자동 전송**: Slack/Email로 매일 아침 자동 리포트 전송
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

**출력 예시**:
```markdown
오늘의 핵심 뉴스 & 수혜주

1순위: Anthropic, AI 모델 개발에 $4B 투자 발표

| 항목     | 내용                              |
|----------|-----------------------------------|
| 뉴스 요약  | AI 스타트업 Anthropic 대규모 투자   |
| 수혜 종목  | 삼성전자 (005930), SK하이닉스 (000660) |
| 연결 고리  | AI 칩 수요 증가 → HBM 수혜        |
| 예상 영향  | 상승, 강도(상)                    |
| 매매 전략  | 시초가 매수                       |
```

---

### Scenario 2: FOMC 특별 리포트

**대상**: 금리 정책 관심 투자자

**실행 시**: FOMC 회의 기간 또는 주요 금리 이벤트 전후

**프로필 설정**:
```bash
DIGEST_PROFILE=fomc
```

**특화 분석**:
- 연준(Fed) 관련 뉴스 집중 수집
- 금리, 인플레이션, 채권 시장 동향
- 시간 범위 확장 (36시간)

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
DIGEST_PROFILE=earnings
```

**특화 분석**:
- 글로벌 기업 실적 발표 모니터링
- 가이던스, 컨센서스 대비 서프라이즈 분석
- 국내 연관주 영향 분석

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
DIGEST_PROFILE=china-policy
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
DIGEST_PROFILE=geopolitical
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
```

### 데이터 흐름

1. **뉴스 수집** (fetch_recent_news)
   - GDELT API에서 최근 24시간 뉴스 검색
   - 키워드 + 테마 쿼리 조합
   - 최대 120개 수집 → 상위 70개 선별

2. **AI 분석** (generate_digest)
   - Google Gemini 2.5 Flash API 호출
   - RICE 프롬프트 기반 구조화된 분석
   - 표 형식의 투자 인사이트 생성

3. **리포트 전송** (send_to_slack / send_email)
   - Slack Webhook으로 실시간 전송
   - 이메일로 백업 전송
   - 3500자 단위로 청크 분할

4. **모니터링** (write_run_report)
   - JSON/Markdown 리포트 생성
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

#### SMTP 이메일 (선택)
```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASS="your-app-password"
export MAIL_FROM="sender@gmail.com"
export MAIL_TO="recipient@gmail.com"
```

### 3. 로컬 실행

#### 기본 프로필 실행
```bash
python digest.py
```

#### 특정 프로필 실행
```bash
# FOMC 리포트
DIGEST_PROFILE=fomc python digest.py

# 실적 시즌 리포트
DIGEST_PROFILE=earnings python digest.py

# 중국 정책 리포트
DIGEST_PROFILE=china-policy python digest.py
```

#### 설정 커스터마이징
```bash
# 시간 범위 변경 (기본: 24시간)
TIME_WINDOW_HOURS=48 python digest.py

# 모델 변경 (기본: gemini-2.5-flash)
GEMINI_MODEL=gemini-1.5-pro python digest.py
```

### 4. GitHub Actions 설정

#### Repository Secrets 추가
`Settings → Secrets and variables → Actions`에서:

```
GOOGLE_API_KEY: your-google-api-key
SLACK_WEBHOOK_URL: your-slack-webhook (선택)
SMTP_HOST: smtp.gmail.com (선택)
SMTP_PORT: 587 (선택)
SMTP_USER: your-email (선택)
SMTP_PASS: your-password (선택)
MAIL_FROM: sender@gmail.com (선택)
MAIL_TO: recipient@gmail.com (선택)
```

#### Repository Variables 추가 (선택)
```
DIGEST_PROFILE: default (또는 fomc, earnings 등)
```

#### 수동 실행
1. `Actions` 탭 이동
2. "Daily Trading Digest" 선택
3. `Run workflow` 클릭

#### 스케줄 변경
`.github/workflows/daily-digest.yml` 파일 수정:
```yaml
on:
  schedule:
    - cron: '30 22 * * *'  # 07:30 KST (UTC-9)
```

---

## 📂 프로젝트 구조

```
Daily-Digest/
├── digest.py                    # 메인 스크립트
├── requirements.txt             # Python 의존성
├── config/
│   ├── settings.json           # 전역 설정
│   ├── keywords.json           # 기본 키워드
│   ├── prompts/
│   │   └── digest_rice.md      # AI 프롬프트 (RICE 포맷)
│   └── profiles/               # 시나리오별 프로필
│       ├── default.json        # 기본 프로필
│       ├── fomc.json           # FOMC 특화
│       ├── earnings.json       # 실적 시즌 특화
│       ├── china-policy.json   # 중국 정책 특화
│       └── geopolitical.json   # 지정학 리스크 특화
├── artifacts/                  # 실행 리포트 저장
│   ├── delivery-report-*.json
│   └── delivery-report-*.md
└── .github/
    └── workflows/
        └── daily-digest.yml    # GitHub Actions 워크플로우
```

---

## ⚙️ 설정 파일 설명

### config/settings.json
```json
{
  "time_window_hours": 24,        // 뉴스 수집 시간 범위
  "max_gdelt_records": 120,       // GDELT API 최대 검색 개수
  "max_news_in_context": 70,      // AI에 전달할 뉴스 개수
  "slack_chunk_size": 3500,       // Slack 메시지 분할 크기
  "theme_query": "(economy OR market OR policy)"  // GDELT 테마 필터
}
```

### config/keywords.json
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

### config/profiles/custom.json (커스텀 프로필 예시)
```json
{
  "settings": {
    "time_window_hours": 48,
    "theme_query": "(technology OR innovation)"
  },
  "keywords": [
    "5g",
    "quantum computing",
    "blockchain"
  ],
  "prompt_file": "prompts/digest_rice.md"
}
```

---

## 🎨 프롬프트 커스터마이징

### RICE 프롬프트 구조

프롬프트는 `config/prompts/digest_rice.md`에서 수정 가능:

```markdown
### R (Role) - 역할
당신은 10년 경력의 트레이딩 전문가입니다.

### I (Instruction) - 지시사항
오늘 주식장 시작 전, 매매에 활용할 수 있는 핵심 정보를 분석해주세요.

### C (Context) - 맥락
- 장 시작 전 30분~1시간 내 빠른 의사결정 필요
- 단타 매매 (당일~2-3일 보유) 관점

### E (Example) - 출력 형식
[표 형식의 구조화된 출력]
```

---

## 📊 출력 예시

### 일일 다이제스트 리포트

<details>
<summary>전체 리포트 보기 (클릭)</summary>

```markdown
# 오늘의 핵심 뉴스 & 수혜주

## 1순위: Anthropic, AI 개발에 $4B 투자 발표

| 항목     | 내용                                    |
|----------|-----------------------------------------|
| 뉴스 요약  | AI 스타트업 Anthropic 대규모 투자 유치    |
| 수혜 종목  | 삼성전자 (005930), SK하이닉스 (000660)   |
| 연결 고리  | AI 칩(HBM) 수요 급증 → 메모리 반도체 수혜 |
| 예상 영향  | 상승, 강도(상)                          |
| 매매 전략  | 시초가 매수                             |
| 목표가    | 삼성전자 80,000원, SK하이닉스 230,000원  |
| 손절가    | 5% 하락 시                              |

---

## 테마별 정리

| 테마           | 관련 뉴스                   | 핵심 종목                    | 강도  |
|----------------|----------------------------|------------------------------|------|
| AI/반도체 테마  | Anthropic 투자, MACOM 전망  | 삼성전자, SK하이닉스         | ***  |
| 지정학 테마     | 미-중 긴장, 인도 영토 인정   | 한화에어로스페이스, LIG넥스원 | **   |
| 실적 테마       | Nio 흑자 기대               | LG에너지솔루션, 에코프로     | **   |

---

## 오늘의 단타 전략 요약

1. **최우선 관심**: AI 관련주 (반도체) - Anthropic 투자 모멘텀
2. **차선 관심**: 방산주 - 지정학적 긴장 고조
3. **시장 분위기**: 혼조 (기술주 강세, 지정학 리스크)
4. **주의사항**: 미국 금리 정책 불확실성 지속
```

</details>

---

## 🔧 고급 사용법

### 1. 멀티 프로필 동시 실행

여러 시나리오를 동시에 분석하려면 별도의 워크플로우 생성:

```yaml
# .github/workflows/multi-digest.yml
jobs:
  default-digest:
    uses: ./.github/workflows/daily-digest.yml
    with:
      profile: default

  fomc-digest:
    uses: ./.github/workflows/daily-digest.yml
    with:
      profile: fomc
```

### 2. 웹훅 통합

Slack 외 다른 서비스 연동:

```python
# digest.py에 추가
def send_to_discord(text: str):
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    payload = {"content": text}
    requests.post(webhook, json=payload)
```

### 3. 데이터베이스 저장

분석 결과를 DB에 저장하여 히스토리 관리:

```python
import sqlite3

def save_to_db(digest: str, news_count: int):
    conn = sqlite3.connect('digests.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO digests (content, news_count, created_at) VALUES (?, ?, ?)",
        (digest, news_count, datetime.now())
    )
    conn.commit()
```

---

## 🐛 트러블슈팅

### GDELT API 오류

**문제**: `Your query was too short or too long`

**해결**:
1. 키워드 개수 줄이기 (최대 10개 권장)
2. 각 키워드 최소 3자 이상
3. `theme_query` 단순화

```json
{
  "theme_query": "(economy OR market)"  // 간결하게
}
```

### Gemini API 오류

**문제**: `Rate limit exceeded`

**해결**:
- 무료 tier 제한: 분당 15 요청, 일일 1,500 요청
- GitHub Actions 실행 빈도 조정 (1일 1회 권장)
- 유료 플랜 고려

### 한글 키워드 문제

**문제**: GDELT API가 한글 키워드 거부

**해결**:
- 영문 키워드만 사용
- `build_query()` 함수가 자동으로 ASCII 필터링

---

## 📈 성능 최적화

### API 비용 절감

| 항목                   | 무료 Tier    | 최적화 방법                  |
|------------------------|--------------|------------------------------|
| Gemini API 요청        | 1,500/day    | 1일 1회 실행 권장             |
| GDELT API 요청         | 무제한       | 캐싱 불필요                  |
| Slack 메시지 전송      | 무제한       | 3500자 단위 분할 전송         |

### 응답 속도 개선

```python
# 병렬 처리 예시 (digest.py 개선안)
import concurrent.futures

def fetch_news_parallel(keywords_batch):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_news, kw) for kw in keywords_batch]
        return [f.result() for f in futures]
```

---

## 🤝 기여 방법

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 라이선스

이 프로젝트는 개인 사용 목적으로 제작되었습니다.

---

## 🙏 참고 자료

- [GDELT API Documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [Google Gemini API Guide](https://ai.google.dev/docs)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

---

## 📧 연락처

문의사항이나 버그 리포트는 GitHub Issues에 등록해주세요.

**Made with ❤️ by Claude Sonnet 4.5**
