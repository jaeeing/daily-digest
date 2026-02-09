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
from notion_client import Client as NotionClient


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


def parse_line_with_links(line: str) -> List[dict]:
    """
    Parse a line and convert HTML links to Notion rich_text format.
    Returns list of rich_text objects with proper link formatting.
    """
    import re

    rich_text = []
    # Pattern to match <a href="url">text</a>
    link_pattern = r'<a\s+href="([^"]*)">([^<]*)</a>'

    last_end = 0
    for match in re.finditer(link_pattern, line):
        # Add text before the link
        if match.start() > last_end:
            plain_text = line[last_end:match.start()]
            if plain_text:
                rich_text.append({
                    "type": "text",
                    "text": {"content": plain_text}
                })

        # Add the link
        url = match.group(1)
        link_text = match.group(2)
        rich_text.append({
            "type": "text",
            "text": {
                "content": link_text,
                "link": {"url": url}
            }
        })
        last_end = match.end()

    # Add remaining text after last link
    if last_end < len(line):
        remaining = line[last_end:]
        if remaining:
            rich_text.append({
                "type": "text",
                "text": {"content": remaining}
            })

    # If no links found, return plain text
    if not rich_text:
        rich_text = [{"type": "text", "text": {"content": line}}]

    return rich_text


def markdown_to_notion_blocks(text: str) -> List[dict]:
    """
    Convert markdown text to Notion blocks.
    Handles headings, paragraphs, horizontal rules, lists, and HTML links.
    Converts <a> tags to Notion's link format, removes other HTML tags.
    """
    import re

    # Remove <div> tags but keep content
    text = re.sub(r'<div[^>]*>', '', text)
    text = re.sub(r'</div>', '', text)
    # Remove other HTML tags except <a> (we'll handle those specially)
    text = re.sub(r'<(?!a\s)(?!/a>)[^>]+>', '', text)

    blocks = []
    lines = text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Heading 1
        if line.startswith('# '):
            content = line[2:].strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": parse_line_with_links(content)
                }
            })
        # Heading 2
        elif line.startswith('## '):
            content = line[3:].strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": parse_line_with_links(content)
                }
            })
        # Heading 3
        elif line.startswith('### '):
            content = line[4:].strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_line_with_links(content)
                }
            })
        # Horizontal rule
        elif line.strip() == '---':
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
        # Skip table separator lines (e.g., |------|------|)
        elif line.strip().startswith('|') and '-' in line and line.count('-') > 3:
            i += 1
            continue
        # Bulleted list
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            content = line.strip()[2:].strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": parse_line_with_links(content)
                }
            })
        # Numbered list
        elif len(line) > 2 and line[0].isdigit() and line[1:3] in ['. ', ') ']:
            content = line[3:].strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": parse_line_with_links(content)
                }
            })
        # Non-empty paragraph
        elif line.strip():
            # Notion has a 2000 character limit per rich_text object
            content = line.strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": parse_line_with_links(content)
                }
            })

        i += 1

    return blocks


def extract_table_value(text: str, section_marker: str, row_key: str) -> str:
    """Extract value from markdown table in a specific section."""
    try:
        # Find the section
        section_start = text.find(section_marker)
        if section_start == -1:
            return ""

        # Find the next section or end
        next_section = text.find("\n## ", section_start + len(section_marker))
        section_text = text[section_start:next_section] if next_section != -1 else text[section_start:]

        # Find the row with the key
        for line in section_text.split('\n'):
            if line.strip().startswith(f"| {row_key}"):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    return parts[2]  # Value is in the 3rd column
        return ""
    except Exception:
        return ""


def fetch_realtime_market_data() -> dict:
    """
    Fetch real-time market data from Yahoo Finance using direct API.

    Returns dict with: vix, sp500, kospi, usdkrw, bond_10y
    Returns 0.0 for any failed fetches.
    """
    data = {
        "vix": 0.0,
        "sp500": 0.0,
        "kospi": 0.0,
        "usdkrw": 0.0,
        "bond_10y": 0.0
    }

    try:
        import yfinance as yf

        # Use download function which is more reliable
        symbols = {
            "^VIX": "vix",
            "^GSPC": "sp500",
            "^KS11": "kospi",
            "KRW=X": "usdkrw",
            "^TNX": "bond_10y"
        }

        for symbol, key in symbols.items():
            try:
                ticker_data = yf.download(symbol, period="5d", progress=False, show_errors=False)
                if not ticker_data.empty:
                    value = ticker_data['Close'].iloc[-1]

                    if key == "vix":
                        data[key] = round(value, 2)
                    elif key == "sp500":
                        data[key] = round(value, 1)
                    elif key == "kospi":
                        data[key] = round(value, 0)
                    elif key == "usdkrw":
                        data[key] = round(value, 0)
                    elif key == "bond_10y":
                        # TNX returns percentage (e.g., 4.25), convert to decimal
                        data[key] = round(value / 100, 4)

            except Exception as e:
                logging.warning(f"Failed to fetch {symbol}: {e}")

        if data["vix"] > 0 or data["sp500"] > 0:
            logging.info(f"Fetched market data: VIX={data['vix']}, S&P500={data['sp500']}, KOSPI={data['kospi']}, USD/KRW={data['usdkrw']}, 10Y={data['bond_10y']}")
        else:
            logging.warning("No market data fetched - all values are 0.0")

    except ImportError:
        logging.warning("yfinance not installed, skipping real-time market data fetch")
    except Exception as e:
        logging.error(f"Error fetching market data: {e}")

    return data


def extract_digest_properties(text: str) -> dict:
    """Extract structured properties from digest markdown text."""
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    date_str = now_kst.strftime("%Y-%m-%d")

    # Extract 한줄 요약 from "시장 레짐" section
    summary = ""
    summary_match = text.find("💡 한줄 요약:")
    if summary_match != -1:
        summary_end = text.find("\n", summary_match)
        if summary_end != -1:
            summary = text[summary_match + 11:summary_end].strip()

    # Extract values from "시장 레짐 & 온도" table
    market_mode_raw = extract_table_value(text, "## 0. 시장 레짐", "시장 모드")
    global_sentiment_raw = extract_table_value(text, "## 0. 시장 레짐", "글로벌 심리")
    vix_str = extract_table_value(text, "## 0. 시장 레짐", "변동성 환경")

    # Clean up select field values - extract only the key word, not explanations
    # Split by common separators and take the first word
    import re
    market_mode = market_mode_raw.split('(')[0].split('—')[0].split('/')[0].strip() if market_mode_raw else ""
    global_sentiment = global_sentiment_raw.split('(')[0].split('—')[0].split('/')[0].strip() if global_sentiment_raw else ""

    # Extract VIX number
    vix = 0.0
    if vix_str and "VIX" in vix_str:
        import re
        vix_match = re.search(r'(\d+\.?\d*)', vix_str)
        if vix_match:
            vix = float(vix_match.group(1))

    # Extract market indices from text
    sp500 = 0.0
    kospi = 0.0
    usdkrw = 0.0
    bond_10y = 0.0

    # Look for S&P 500 variations - only extract if value is realistic (> 1000)
    sp_patterns = [r'S&P\s*500[:\s]+(\d{4,5}\.?\d*)', r'S&P[:\s]+(\d{4,5}\.?\d*)']
    for pattern in sp_patterns:
        sp_match = re.search(pattern, text, re.IGNORECASE)
        if sp_match:
            value = float(sp_match.group(1))
            if value > 1000:  # Sanity check
                sp500 = value
                break

    # Look for KOSPI - only extract if value is realistic (> 1000)
    kospi_match = re.search(r'KOSPI[:\s]+(\d{4,5}\.?\d*)', text, re.IGNORECASE)
    if kospi_match:
        value = float(kospi_match.group(1))
        if value > 1000:  # Sanity check
            kospi = value

    # Look for USD/KRW - only extract if value is realistic (1000-2000)
    usdkrw_patterns = [r'USD/KRW[:\s]+(\d{4}\.?\d*)', r'원달러[:\s]+(\d{4}\.?\d*)']
    for pattern in usdkrw_patterns:
        usd_match = re.search(pattern, text, re.IGNORECASE)
        if usd_match:
            value = float(usd_match.group(1))
            if 1000 <= value <= 2000:  # Sanity check for won/dollar
                usdkrw = value
                break

    # Look for 10Y bond yield - only extract if value is realistic (0.5-10%)
    bond_patterns = [r'10Y[:\s]+(\d+\.?\d*)%', r'10년물[:\s]+(\d+\.?\d*)%']
    for pattern in bond_patterns:
        bond_match = re.search(pattern, text, re.IGNORECASE)
        if bond_match:
            value = float(bond_match.group(1))
            # Value should be between 0.5 and 10 for realistic bond yields
            if 0.5 <= value <= 10:
                bond_10y = value / 100  # Convert to decimal
                break

    # Extract 시장 분위기 from "오늘의 단타 전략"
    market_atmosphere = ""
    atm_match = text.find("**시장 분위기**:")
    if atm_match != -1:
        atm_end = text.find("\n", atm_match)
        if atm_end != -1:
            atm_line = text[atm_match:atm_end]
            # Extract first word after "분위기**: "
            parts = atm_line.split("**: ")
            if len(parts) > 1:
                market_atmosphere = parts[1].split(" ")[0].strip()

    # Extract 분석 확신도 from "시장 레짐 & 온도" table (overall digest confidence)
    confidence = ""
    confidence_str = extract_table_value(text, "## 0. 시장 레짐", "분석 확신도")
    if confidence_str:
        # Normalize confidence to match Notion select options
        # Count filled stars (★) to determine level
        filled_stars = confidence_str.count('★')
        if filled_stars == 5:
            confidence = "★★★★★ (90%+)"
        elif filled_stars == 4:
            confidence = "★★★★☆ (70-89%)"
        elif filled_stars == 3:
            confidence = "★★★☆☆ (50-69%)"
        elif filled_stars == 2:
            confidence = "★★☆☆☆ (30-49%)"
        elif filled_stars == 1:
            confidence = "★☆☆☆☆ (<30%)"
        else:
            # If already in correct format, use as is
            confidence = confidence_str if confidence_str else "정보 없음"

    # Extract 최우선 관심 종목
    priority_stocks = ""
    priority_match = text.find("**🎯 최우선 관심**:")
    if priority_match != -1:
        priority_end = text.find("\n", priority_match)
        if priority_end != -1:
            priority_line = text[priority_match + 16:priority_end]
            # Extract stock names/codes
            import re
            # Find patterns like "종목명 (코드)" or just "종목명"
            stocks = re.findall(r'[\w가-힣]+\s*\([A-Z0-9]+\)', priority_line)
            if stocks:
                priority_stocks = ", ".join(stocks[:3])  # Top 3

    # Extract keywords from first few sections
    keywords = []
    # Look for common themes in headings
    for keyword in ["반도체", "금리", "AI", "지정학", "실적", "금", "원자재", "로테이션", "정치", "중국"]:
        if keyword in text[:2000]:  # Check in first part of text
            keywords.append(keyword)

    # Fetch real-time market data as fallback if text extraction failed
    if vix == 0.0 or sp500 == 0.0 or kospi == 0.0 or usdkrw == 0.0 or bond_10y == 0.0:
        logging.info("Text extraction incomplete, fetching real-time market data...")
        realtime_data = fetch_realtime_market_data()

        # Use real-time data as fallback
        if vix == 0.0 and realtime_data["vix"] > 0:
            vix = realtime_data["vix"]
        if sp500 == 0.0 and realtime_data["sp500"] > 0:
            sp500 = realtime_data["sp500"]
        if kospi == 0.0 and realtime_data["kospi"] > 0:
            kospi = realtime_data["kospi"]
        if usdkrw == 0.0 and realtime_data["usdkrw"] > 0:
            usdkrw = realtime_data["usdkrw"]
        if bond_10y == 0.0 and realtime_data["bond_10y"] > 0:
            bond_10y = realtime_data["bond_10y"]

    # Market data extracted from text
    properties = {
        "제목": f"[{date_str}] {summary[:100] if summary else '일일 트레이딩 다이제스트'}",
        "date:날짜:start": date_str,
        "date:날짜:is_datetime": 0,
        "시장 모드": market_mode or "정보 없음",
        "글로벌 심리": global_sentiment or "정보 없음",
        "VIX": vix,
        "S&P500": sp500,
        "KOSPI": kospi,
        "USD/KRW": usdkrw,
        "10Y 금리": bond_10y,
        "확신도": confidence or "정보 없음",
        "시장 분위기": market_atmosphere or "정보 없음",
        "핵심 키워드": json.dumps(keywords[:6], ensure_ascii=False),
        "최우선 관심 종목": priority_stocks or "정보 없음",
        "한줄 요약": summary or "일일 시장 분석"
    }

    return properties


def send_to_notion(text: str) -> DeliveryStatus:
    """
    Send digest content to Notion using data_source_id.

    Environment variables needed:
    - NOTION_TOKEN: Notion Integration Token
    - NOTION_DATA_SOURCE_ID: Target data source ID
    """
    token = os.getenv("NOTION_TOKEN")
    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID")

    if not token or not data_source_id:
        logging.info("Notion env vars not set, skipping Notion delivery")
        return DeliveryStatus(
            enabled=False,
            attempted=False,
            success=False,
            detail="notion_not_configured"
        )

    try:
        notion = NotionClient(auth=token)

        # Extract structured properties from markdown
        logging.info("Extracting digest properties...")
        props_raw = extract_digest_properties(text)

        # Parse keywords from JSON string
        keywords_list = []
        try:
            keywords_list = json.loads(props_raw["핵심 키워드"])
        except:
            keywords_list = []

        # Convert to Notion property format
        properties = {
            "제목": {
                "title": [{"text": {"content": props_raw["제목"]}}]
            },
            "날짜": {
                "date": {"start": props_raw["date:날짜:start"]}
            },
            "시장 모드": {
                "select": {"name": props_raw["시장 모드"]}
            },
            "글로벌 심리": {
                "select": {"name": props_raw["글로벌 심리"]}
            },
            "VIX": {
                "number": props_raw["VIX"]
            },
            "S&P500": {
                "number": props_raw["S&P500"]
            },
            "KOSPI": {
                "number": props_raw["KOSPI"]
            },
            "USD/KRW": {
                "number": props_raw["USD/KRW"]
            },
            "10Y 금리": {
                "number": props_raw["10Y 금리"]
            },
            "확신도": {
                "select": {"name": props_raw["확신도"]}
            },
            "시장 분위기": {
                "select": {"name": props_raw["시장 분위기"]}
            },
            "핵심 키워드": {
                "multi_select": [{"name": kw} for kw in keywords_list]
            },
            "최우선 관심 종목": {
                "rich_text": [{"text": {"content": props_raw["최우선 관심 종목"]}}]
            },
            "한줄 요약": {
                "rich_text": [{"text": {"content": props_raw["한줄 요약"]}}]
            }
        }

        # Convert markdown to Notion blocks
        logging.info("Converting markdown to Notion blocks...")
        children = markdown_to_notion_blocks(text)

        # Create page using standard Notion structure
        # (treating data_source_id as database_id for now)
        logging.info("Creating Notion page: %s", props_raw["제목"])

        payload = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": data_source_id
            },
            "properties": properties,
            "children": children[:100]  # Notion has limit on children blocks
        }

        # Use direct API call since notion-client might not support this structure yet
        import requests
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            json=payload,
            timeout=30
        )

        if not response.ok:
            logging.error("Notion API error response: %s", response.text)

        response.raise_for_status()
        result = response.json()

        page_id = result.get("id", "unknown")
        logging.info("Notion page created with ID: %s", page_id)

        return DeliveryStatus(
            enabled=True,
            attempted=True,
            success=True,
            detail=f"page_id={page_id[:8]}..., title={props_raw['제목'][:30]}"
        )

    except Exception as exc:
        logging.error("Failed to send to Notion: %s", exc, exc_info=True)
        return DeliveryStatus(
            enabled=True,
            attempted=True,
            success=False,
            detail=f"error: {str(exc)[:100]}"
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
        f"- notion: `{report['delivery']['notion']['detail']}` (success={report['delivery']['notion']['success']})",
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
            "notion": {"enabled": False, "attempted": False, "success": False, "detail": "not_attempted"},
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

        try:
            notion_status = send_to_notion(digest)
            report["delivery"]["notion"] = notion_status.__dict__
        except Exception as exc:
            report["delivery"]["notion"] = DeliveryStatus(
                enabled=True, attempted=True, success=False, detail=f"error={exc}"
            ).__dict__

        # Check if all delivery methods failed
        all_failed = all(
            delivery["attempted"] and not delivery["success"]
            for delivery in report["delivery"].values()
            if delivery["attempted"]
        )
        if all_failed and any(d["attempted"] for d in report["delivery"].values()):
            raise RuntimeError("All delivery methods failed.")

        report["status"] = "success"
        print(digest)
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        write_run_report(report)


if __name__ == "__main__":
    main()
