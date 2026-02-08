import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path
from typing import Any, List

import requests
from google import genai
import markdown
from premailer import transform


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "config"))
REPORT_DIR = Path(os.getenv("REPORT_DIR", "artifacts"))
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"

DEFAULT_KEYWORDS = [
    "금리",
    "연준",
    "inflation",
    "물가",
    "환율",
    "달러",
    "채권",
    "국채",
    "나스닥",
    "반도체",
    "s&p",
    "ai",
    "경기침체",
    "고용",
    "pmi",
    "federal reserve",
    "china policy",
    "commodity",
    "geopolitical risk",
]

DEFAULT_PROMPT_RICE = """### R (Role) - 역할

당신은 10년 경력의 트레이딩 전문가입니다.

* 매일 새벽 글로벌 뉴스와 공시를 분석
* 테마주/이슈 선점 투자 전문
* 정치/경제 이벤트 -> 수혜주 연결 분석 능력

### I (Instruction) - 지시사항

오늘 주식장 시작 전, 매매에 활용할 수 있는 핵심 정보를 분석해주세요.

중요: 최근 24시간 이내의 최신 뉴스를 실시간 검색하여 분석해주세요.

분석 조건:

* 뉴스 유형: 글로벌이슈, 정치, 테마
* 미국 증시, 중국 정책, 환율, 원자재, 지정학 리스크
* 주요키워드 : 금리, 연준, inflation, 물가, 환율, 달러, 채권, 국채, 나스닥, 반도체, s&p, ai, 경기침체, 고용, pmi
* 시장: 전체 (한국 + 미국 + 글로벌 전체 시장)

찾아야 할 정보:

1. 정치인 발언/행동 -> 관련 수혜주 (예: 대통령이 특정 기업 방문, 선물 증정 등)
2. 새벽 공시 중 주가에 영향 줄 내용 (계약, 실적, 인수합병)
3. 해외 시장 마감 후 나온 뉴스 중 국내 영향
4. SNS/커뮤니티에서 화제되는 테마
5. 전일 시간외 거래에서 급등/급락한 종목

### C (Context) - 맥락

* 장 시작 전 30분~1시간 내 빠른 의사결정 필요
* 단타 매매 (당일~2-3일 보유) 관점
* 뉴스 -> 종목 연결이 핵심 (왜 이 종목이 움직일지)

### E (Example) - 출력 형식

오늘의 핵심 뉴스 & 수혜주
"""


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str


@dataclass
class DeliveryStatus:
    enabled: bool
    attempted: bool
    success: bool
    detail: str


@dataclass
class RuntimeConfig:
    profile: str
    time_window_hours: int
    max_gdelt_records: int
    max_news_in_context: int
    slack_chunk_size: int
    keywords: List[str]
    theme_query: str
    prompt_rice: str
    prompt_path: str


def iso_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_gdelt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        logging.warning("Config file not found: %s", path)
        return {}

    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
        if isinstance(data, dict):
            return data
        logging.warning("Invalid config format (dict expected): %s", path)
        return {}


def load_text(path: Path, fallback: str) -> str:
    if not path.exists():
        logging.warning("Prompt file not found: %s", path)
        return fallback
    return path.read_text(encoding="utf-8").strip() or fallback


def resolve_prompt_path(profile_cfg: dict[str, Any]) -> Path:
    prompt_rel = profile_cfg.get("prompt_file", "prompts/digest_rice.md")
    return CONFIG_DIR / str(prompt_rel)


def load_runtime_config() -> RuntimeConfig:
    profile_name = os.getenv("DIGEST_PROFILE", "default").strip() or "default"
    settings = load_json(CONFIG_DIR / "settings.json")
    keyword_cfg = load_json(CONFIG_DIR / "keywords.json")
    profile_cfg = load_json(CONFIG_DIR / "profiles" / f"{profile_name}.json")

    profile_settings = profile_cfg.get("settings", {})
    prompt_path = resolve_prompt_path(profile_cfg)
    prompt_rice = load_text(prompt_path, DEFAULT_PROMPT_RICE)

    time_window_hours = int(
        os.getenv("TIME_WINDOW_HOURS", profile_settings.get("time_window_hours", settings.get("time_window_hours", 24)))
    )
    max_gdelt_records = int(
        os.getenv("MAX_GDELT_RECORDS", profile_settings.get("max_gdelt_records", settings.get("max_gdelt_records", 120)))
    )
    max_news_in_context = int(
        os.getenv(
            "MAX_NEWS_IN_CONTEXT",
            profile_settings.get("max_news_in_context", settings.get("max_news_in_context", 70)),
        )
    )
    slack_chunk_size = int(
        os.getenv("SLACK_CHUNK_SIZE", profile_settings.get("slack_chunk_size", settings.get("slack_chunk_size", 3500)))
    )

    raw_keywords = profile_cfg.get("keywords", keyword_cfg.get("keywords", DEFAULT_KEYWORDS))
    keywords = [str(x).strip() for x in raw_keywords if str(x).strip()]
    if not keywords:
        keywords = DEFAULT_KEYWORDS

    theme_query = str(
        profile_settings.get(
            "theme_query",
            settings.get(
                "theme_query",
                "(politics OR geopolitical OR economy OR market OR earnings OR m&a OR guidance OR disclosure OR policy)",
            ),
        )
    ).strip()

    logging.info("Loaded profile=%s prompt=%s keyword_count=%d", profile_name, prompt_path, len(keywords))

    return RuntimeConfig(
        profile=profile_name,
        time_window_hours=time_window_hours,
        max_gdelt_records=max_gdelt_records,
        max_news_in_context=max_news_in_context,
        slack_chunk_size=slack_chunk_size,
        keywords=keywords,
        theme_query=theme_query,
        prompt_rice=prompt_rice,
        prompt_path=str(prompt_path),
    )


def build_query(cfg: RuntimeConfig) -> str:
    # Filter out non-ASCII keywords and very short keywords (GDELT API rejects them)
    english_keywords = [kw for kw in cfg.keywords if kw.isascii() and len(kw) >= 3]
    if not english_keywords:
        logging.warning("No valid ASCII keywords found, using fallback")
        english_keywords = ["inflation", "economy", "market"]

    keyword_query = " OR ".join(f'"{kw}"' for kw in english_keywords)
    return f"({keyword_query}) AND {cfg.theme_query}"


def fetch_recent_news(cfg: RuntimeConfig) -> List[NewsItem]:
    end_dt = iso_utc_now()
    start_dt = end_dt - timedelta(hours=cfg.time_window_hours)

    query = build_query(cfg)
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": str(cfg.max_gdelt_records),
        "startdatetime": to_gdelt_dt(start_dt),
        "enddatetime": to_gdelt_dt(end_dt),
    }

    logging.info("Fetching GDELT articles between %s and %s UTC", start_dt.isoformat(), end_dt.isoformat())
    logging.info("GDELT query: %s", query)
    resp = requests.get(GDELT_ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()

    if not resp.text.strip():
        logging.warning("GDELT returned empty response")
        return []

    try:
        payload = resp.json()
    except ValueError as exc:
        logging.error("Failed to parse GDELT JSON response: %s", exc)
        logging.error("Response text: %s", resp.text[:500])
        return []

    articles = payload.get("articles", [])
    news_items: List[NewsItem] = []

    for row in articles[: cfg.max_news_in_context]:
        title = (row.get("title") or "").strip()
        url = (row.get("url") or "").strip()
        if not title or not url:
            continue

        source = (row.get("domain") or row.get("sourcecountry") or "unknown").strip()
        published_at = (row.get("seendate") or row.get("socialimage") or "unknown").strip()
        news_items.append(
            NewsItem(
                title=title,
                url=url,
                source=source,
                published_at=published_at,
            )
        )

    logging.info("Fetched %d candidate articles", len(news_items))
    return news_items


def build_news_context(news_items: List[NewsItem]) -> str:
    lines = []
    for i, item in enumerate(news_items, 1):
        lines.append(
            f"[{i}] 제목: {item.title}\\n"
            f"- 출처: {item.source}\\n"
            f"- 시간: {item.published_at}\\n"
            f"- 링크: {item.url}"
        )
    return "\\n\\n".join(lines)


def generate_digest(news_items: List[NewsItem], prompt_rice: str) -> str:
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is required")

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    context = build_news_context(news_items)

    system_instruction = "당신은 신중한 금융 리서치 보조자입니다. 주어진 뉴스 근거를 벗어나 추측하지 말고, 불확실한 값은 명확히 표시하세요."

    user_input = (
        f"{prompt_rice}\\n\\n"
        "아래는 최근 24시간 뉴스 후보 목록입니다. 반드시 이 목록을 우선 근거로 분석하세요.\\n"
        "출력은 Example 형식을 최대한 그대로 유지해 주세요.\\n"
        "현재가/등락 등 실시간 시세가 확실하지 않으면 '확인 필요'로 표기하세요.\\n\\n"
        f"[최근 24시간 뉴스 목록]\\n{context}"
    )

    full_prompt = f"{system_instruction}\\n\\n{user_input}"

    logging.info("Generating digest with model=%s", DEFAULT_MODEL)
    response = client.models.generate_content(model=DEFAULT_MODEL, contents=full_prompt)
    output = response.text.strip()
    if not output:
        raise RuntimeError("Gemini returned empty output")
    return output


def split_for_slack(text: str, chunk_size: int) -> List[str]:
    chunks: List[str] = []
    remaining = text
    while len(remaining) > chunk_size:
        cut = remaining.rfind("\n", 0, chunk_size)
        if cut <= 0:
            cut = chunk_size
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def send_to_slack(text: str, chunk_size: int) -> DeliveryStatus:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        logging.info("SLACK_WEBHOOK_URL not set, skipping Slack delivery")
        return DeliveryStatus(enabled=False, attempted=False, success=False, detail="webhook_not_configured")

    sent_chunks = 0
    for idx, chunk in enumerate(split_for_slack(text, chunk_size), 1):
        payload = {"text": chunk}
        resp = requests.post(webhook, json=payload, timeout=20)
        resp.raise_for_status()
        logging.info("Sent Slack chunk %d", idx)
        sent_chunks += 1

    return DeliveryStatus(
        enabled=True,
        attempted=True,
        success=True,
        detail=f"sent_chunks={sent_chunks}",
    )


def send_email(text: str) -> DeliveryStatus:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    mail_from = os.getenv("MAIL_FROM")
    mail_to = os.getenv("MAIL_TO")

    required = [host, port, user, password, mail_from, mail_to]
    if not all(required):
        logging.info("SMTP env vars incomplete, skipping email delivery")
        return DeliveryStatus(enabled=False, attempted=False, success=False, detail="smtp_not_fully_configured")

    recipients = [addr.strip() for addr in mail_to.split(",") if addr.strip()]
    if not recipients:
        logging.info("MAIL_TO is empty after parsing, skipping email delivery")
        return DeliveryStatus(enabled=False, attempted=False, success=False, detail="mail_to_empty")

    now_kst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
    subject = f"[Daily Trading Digest] {now_kst}"

    # Markdown을 HTML로 변환
    html_content = markdown.markdown(
        text,
        extensions=['tables', 'nl2br', 'fenced_code']
    )

    # 기본 HTML 템플릿 적용
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', '맑은 고딕', 'Segoe UI', Arial, sans-serif;
                font-size: 15px;
                line-height: 1.7;
                color: #2c3e50;
                background-color: #f8f9fa;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            h1 {{
                font-size: 28px;
                color: #ffffff;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: -30px -30px 25px -30px;
                padding: 25px 30px;
                border-radius: 8px 8px 0 0;
                text-align: center;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            h2 {{
                font-size: 22px;
                color: #ffffff;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                margin: 35px -30px 20px -30px;
                padding: 15px 30px;
                border-left: 5px solid #e74c3c;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h3 {{
                font-size: 19px;
                color: #2c3e50;
                margin-top: 30px;
                margin-bottom: 15px;
                padding: 12px 15px;
                background-color: #ecf0f1;
                border-left: 5px solid #3498db;
                border-radius: 4px;
            }}
            p {{
                font-size: 15px;
                line-height: 1.7;
                margin-bottom: 12px;
            }}
            table {{
                border-collapse: separate;
                border-spacing: 0;
                width: 100%;
                margin: 20px 0;
                font-size: 14px;
                background-color: #ffffff;
                border: 2px solid #2c3e50;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            th, td {{
                border: 1px solid #bdc3c7;
                padding: 16px 14px;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: #ffffff;
                font-weight: 700;
                font-size: 15px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: none;
                border-bottom: 3px solid #e74c3c;
            }}
            td:first-child {{
                background-color: #ecf0f1;
                font-weight: 600;
                color: #2c3e50;
                width: 20%;
                border-right: 2px solid #bdc3c7;
            }}
            tr:nth-child(even) td:not(:first-child) {{
                background-color: #f8f9fa;
            }}
            tr:nth-child(odd) td:not(:first-child) {{
                background-color: #ffffff;
            }}
            tr:hover td {{
                background-color: #fff3cd !important;
                transition: background-color 0.2s;
            }}
            tr:hover td:first-child {{
                background-color: #ffeaa7 !important;
            }}
            hr {{
                border: 0;
                height: 3px;
                background: linear-gradient(to right, #667eea, #764ba2, transparent);
                margin: 30px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            code {{
                background-color: #f4f4f4;
                padding: 4px 10px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #ddd;
            }}
            strong {{
                color: #e74c3c;
                font-weight: 700;
                background-color: #ffe5e5;
                padding: 2px 6px;
                border-radius: 3px;
            }}
            p strong {{
                background: none;
                padding: 0;
            }}
            .news-meta {{
                font-size: 14px;
                color: #34495e;
                background-color: #e8f4f8;
                padding: 12px 15px;
                margin: 10px 0 15px 0;
                border-radius: 6px;
                border-left: 4px solid #3498db;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            blockquote {{
                border-left: 4px solid #f39c12;
                padding: 15px 20px;
                margin: 15px 0;
                background-color: #fef5e7;
                border-radius: 4px;
            }}
            ul, ol {{
                margin: 15px 0;
                padding-left: 30px;
                line-height: 1.8;
            }}
            li {{
                margin-bottom: 8px;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
                font-weight: 600;
                border-bottom: 1px solid transparent;
                transition: all 0.2s;
            }}
            a:hover {{
                color: #2980b9;
                border-bottom-color: #2980b9;
            }}
            .news-meta a {{
                color: #2c3e50;
                font-weight: 700;
                text-decoration: underline;
            }}
            .news-meta a:hover {{
                color: #3498db;
            }}
            @media only screen and (max-width: 600px) {{
                body {{ padding: 10px; }}
                .container {{ padding: 20px; }}
                h1 {{ font-size: 20px; }}
                h2 {{ font-size: 18px; }}
                table {{ font-size: 13px; }}
                th, td {{ padding: 10px 8px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {html_content}
        </div>
    </body>
    </html>
    """

    # CSS를 인라인 스타일로 변환 (이메일 클라이언트 호환성)
    html_body_inlined = transform(html_body)

    msg = MIMEText(html_body_inlined, _subtype="html", _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)

    with smtplib.SMTP(host, int(port), timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(mail_from, recipients, msg.as_string())

    logging.info("Email sent to %d recipients", len(recipients))
    return DeliveryStatus(
        enabled=True,
        attempted=True,
        success=True,
        detail=f"recipients={len(recipients)}",
    )


def write_run_report(report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = os.getenv("GITHUB_RUN_ID", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    json_path = REPORT_DIR / f"delivery-report-{run_id}.json"
    md_path = REPORT_DIR / f"delivery-report-{run_id}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_lines = [
        "# Daily Trading Digest Delivery Report",
        "",
        f"- run_id: `{report['run_id']}`",
        f"- timestamp_utc: `{report['timestamp_utc']}`",
        f"- status: `{report['status']}`",
        f"- news_count: `{report['news_count']}`",
        "",
        "## Delivery",
        f"- slack: `{report['delivery']['slack']['detail']}` (success={report['delivery']['slack']['success']})",
        f"- email: `{report['delivery']['email']['detail']}` (success={report['delivery']['email']['success']})",
    ]
    if report.get("error"):
        summary_lines.extend(["", "## Error", f"`{report['error']}`"])

    md_path.write_text("\n".join(summary_lines), encoding="utf-8")
    logging.info("Wrote run reports: %s, %s", json_path, md_path)


def main() -> None:
    cfg = load_runtime_config()

    now_utc = datetime.now(timezone.utc)
    run_id = os.getenv("GITHUB_RUN_ID", "local-run")
    report = {
        "run_id": str(run_id),
        "timestamp_utc": now_utc.isoformat(),
        "status": "failed",
        "news_count": 0,
        "config": {
            "profile": cfg.profile,
            "time_window_hours": cfg.time_window_hours,
            "max_gdelt_records": cfg.max_gdelt_records,
            "max_news_in_context": cfg.max_news_in_context,
            "keyword_count": len(cfg.keywords),
            "prompt_path": cfg.prompt_path,
        },
        "delivery": {
            "slack": {"enabled": False, "attempted": False, "success": False, "detail": "not_attempted"},
            "email": {"enabled": False, "attempted": False, "success": False, "detail": "not_attempted"},
        },
        "error": None,
    }

    try:
        news_items = fetch_recent_news(cfg)
        report["news_count"] = len(news_items)
        if not news_items:
            raise RuntimeError("No recent articles from GDELT. Try broadening keywords or increasing max records.")

        digest = generate_digest(news_items, cfg.prompt_rice)

        try:
            slack_status = send_to_slack(digest, cfg.slack_chunk_size)
            report["delivery"]["slack"] = slack_status.__dict__
        except Exception as exc:
            report["delivery"]["slack"] = DeliveryStatus(
                enabled=True, attempted=True, success=False, detail=f"error={exc}"
            ).__dict__

        try:
            email_status = send_email(digest)
            report["delivery"]["email"] = email_status.__dict__
        except Exception as exc:
            report["delivery"]["email"] = DeliveryStatus(
                enabled=True, attempted=True, success=False, detail=f"error={exc}"
            ).__dict__

        if (
            report["delivery"]["slack"]["attempted"]
            and not report["delivery"]["slack"]["success"]
            and report["delivery"]["email"]["attempted"]
            and not report["delivery"]["email"]["success"]
        ):
            raise RuntimeError("Both Slack and Email delivery failed.")

        report["status"] = "success"
        print(digest)
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        write_run_report(report)


if __name__ == "__main__":
    main()
