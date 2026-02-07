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
from openai import OpenAI


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "config"))
REPORT_DIR = Path(os.getenv("REPORT_DIR", "artifacts"))
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

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

당신은 10년 경력의 단기 트레이딩 전문가입니다.

* 매일 새벽 글로벌 뉴스와 공시를 분석
* 테마주/이슈 선점 투자 전문
* 정치/경제 이벤트 -> 수혜주 연결 분석 능력

### I (Instruction) - 지시사항

오늘 주식장 시작 전, 단타 매매에 활용할 수 있는 핵심 정보를 분석해주세요.

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
    keyword_query = " OR ".join(f'"{kw}"' for kw in cfg.keywords)
    return f"({keyword_query}) AND {cfg.theme_query}"


def fetch_recent_news(cfg: RuntimeConfig) -> List[NewsItem]:
    end_dt = iso_utc_now()
    start_dt = end_dt - timedelta(hours=cfg.time_window_hours)

    params = {
        "query": build_query(cfg),
        "mode": "artlist",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": str(cfg.max_gdelt_records),
        "startdatetime": to_gdelt_dt(start_dt),
        "enddatetime": to_gdelt_dt(end_dt),
    }

    logging.info("Fetching GDELT articles between %s and %s UTC", start_dt.isoformat(), end_dt.isoformat())
    resp = requests.get(GDELT_ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()

    payload = resp.json()
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
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    context = build_news_context(news_items)

    user_input = (
        f"{prompt_rice}\\n\\n"
        "아래는 최근 24시간 뉴스 후보 목록입니다. 반드시 이 목록을 우선 근거로 분석하세요.\\n"
        "출력은 Example 형식을 최대한 그대로 유지해 주세요.\\n"
        "현재가/등락 등 실시간 시세가 확실하지 않으면 '확인 필요'로 표기하세요.\\n\\n"
        f"[최근 24시간 뉴스 목록]\\n{context}"
    )

    logging.info("Generating digest with model=%s", DEFAULT_MODEL)
    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=[
            {
                "role": "system",
                "content": "당신은 신중한 금융 리서치 보조자입니다. 주어진 뉴스 근거를 벗어나 추측하지 말고, 불확실한 값은 명확히 표시하세요.",
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
    )
    output = response.output_text.strip()
    if not output:
        raise RuntimeError("OpenAI returned empty output")
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

    msg = MIMEText(text, _subtype="plain", _charset="utf-8")
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
