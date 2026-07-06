#!/usr/bin/env python3
"""Generate an interactive daily HTML report for Songyuan Safety 300893."""

from __future__ import annotations

import datetime as dt
import html
import io
import json
import pathlib
import re
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "songyuan_security_daily.html"
INDEX_OUTPUT = ROOT / "outputs" / "index.html"
SOURCES = ROOT / "data" / "sources.json"
ANNOUNCEMENT_TEXT_DIR = ROOT / "work" / "announcements"
MAX_ANNOUNCEMENTS_WITH_FULLTEXT = 30
BEIJING_TZ = dt.timezone(dt.timedelta(hours=8))


def fetch_json(url: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 Codex Songyuan Safety Monitor",
            "Referer": "https://www.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode("utf-8", errors="replace").strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return json.loads(text)


def fetch_text(url: str, params: dict[str, str], referer: str) -> str:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 Codex Songyuan Safety Monitor",
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("gbk", errors="replace").strip()


def fetch_bytes(url: str, referer: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Codex Songyuan Safety Monitor",
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def to_float(value: object, div: float = 1) -> float | None:
    try:
        return float(value) / div
    except (TypeError, ValueError):
        return None


def score_item(title: str, content: str, item_type: str, keywords: dict[str, list[str]]) -> tuple[int, list[str], str]:
    text = title + " " + content
    score = 45
    tags = [item_type]
    tone = "neutral"

    if item_type == "公告":
        score += 25
    if any(k in text for k in keywords["highImpact"]):
        score += 25
        tags.append("高影响")
    if any(k in text for k in keywords["positive"]):
        score += 10
        tags.append("利好")
        tone = "green"
    if any(k in text for k in keywords["risk"]):
        score += 12
        tags.append("风险")
        tone = "red"
    if "可转债" in text or "再融资" in text or "募集说明书" in text:
        tags.append("再融资")
        tone = "amber"
    if "分红" in text or "权益分派" in text:
        tags.append("分红")
    if "股权激励" in text or "限制性股票" in text:
        tags.append("股权激励")
    return min(score, 100), sorted(set(tags), key=tags.index), tone


def pdf_url(art_code: str) -> str:
    return f"https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf"


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_announcement_text(art_code: str) -> str:
    if not art_code:
        return ""
    cache_path = ANNOUNCEMENT_TEXT_DIR / f"{art_code}.txt"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    try:
        import pypdf

        pdf_data = fetch_bytes(pdf_url(art_code), "https://data.eastmoney.com/")
        reader = pypdf.PdfReader(io.BytesIO(pdf_data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        text = normalize_text(text)
        ANNOUNCEMENT_TEXT_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text
    except Exception as exc:
        print(f"Announcement PDF text fetch failed for {art_code}: {exc}")
        return ""


def split_key_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    line_parts = []
    for line in text.splitlines():
        line = re.sub(r"\s+", "", line.strip())
        if "..." not in line and "……" not in line:
            line_parts.append(line)

    compact_text = re.sub(r"\s+", "", text)
    raw_parts = line_parts + re.split(r"(?<=[。！？；])", compact_text)
    sentences: list[str] = []
    for part in raw_parts:
        part = re.sub(r"^\s*[（(]?[一二三四五六七八九十\d]+[）)、.．]\s*", "", part.strip())
        part = re.sub(r"\s+", "", part)
        if "..." in part or "……" in part:
            continue
        if 10 <= len(part) <= 220 and not part.startswith(("证券代码", "证券简称", "公告编号", "特此公告")):
            sentences.append(part)
    return sentences


def clean_point(point: str) -> str:
    point = re.sub(r"\s+", "", point)
    point = re.sub(r"本公司及董事会全体成员保证.*?重大遗漏。?", "", point)
    if len(point) > 220:
        split = re.search(r"(?:[一二三四五六七八九十]、|\d+、|《)", point[40:])
        if split:
            point = point[: 40 + split.start()]
    return point.strip(" ，。；、")


def dedupe_points(points: list[str]) -> list[str]:
    cleaned: list[str] = []
    for point in points:
        point = clean_point(point)
        if len(point) < 8:
            continue
        if any(point in old or old in point for old in cleaned):
            continue
        cleaned.append(point)
    return cleaned[:5]


def regex_points(compact_text: str, patterns: list[str]) -> list[str]:
    points: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, compact_text)
        if match:
            points.append(match.group(0))
    return points


def specialized_announcement_points(title: str, full_text: str) -> list[str]:
    compact = re.sub(r"\s+", "", full_text)
    if "最近五年被证券监管部门" in title:
        return dedupe_points(
            regex_points(
                compact,
                [
                    r"公司最近五年不存在被中国证券监督管理委员会和深交所处罚的情况。",
                    r"最近五年，公司共收到一份通报批评、一份警示函和一份监管函，均已按要求履行信息披露义务并已整改落实。",
                    r"公司及相关责任人收到深交所通报批评的决定书[^。]*。",
                    r"公司收到宁波证监局出具警示函[^。]*。",
                    r"公司及相关责任人收到深交所监管函[^。]*。",
                    r"公司承诺：除上述情况外，公司最近五年不存在其他被证券监管部门和证券交易所采取监管措施或处罚的情况。",
                ],
            )
        )

    if "募集说明书" in title:
        points = regex_points(
            compact,
            [
                r"本次发行可转换公司债券方案已经公司董事会和股东会审议通过，尚需证券交易所审核通过以及中国证监会作出同意注册的决定后方可实施。",
                r"本次发行募集资金总额不超过人民币105,500\.00万元（含本数）[^。]*。",
            ],
        )
        if "年产1520万套汽车安全系统核心部件全产业链配套项目" in compact:
            points.append("募投项目包括：年产1520万套汽车安全系统核心部件全产业链配套项目拟使用募集资金73,850.00万元，补充流动资金项目拟使用31,650.00万元。")
        points.extend(
            regex_points(
                compact,
                [
                    r"公司聘请联合资信为本次发行的可转债进行了信用评级，本次可转债主体信用评级为A\+级，债券信用评级为A\+级。",
                    r"本次发行的可转债不提供担保。",
                    r"公司本次募投项目将新增汽车安全带、汽车安全气囊和汽车方向盘产品产能[^。]*。",
                ],
            )
        )
        return dedupe_points(points)

    if "可转换公司债券申请获得深圳证券交易所受理" in title:
        return dedupe_points(
            regex_points(
                compact,
                [
                    r"深交所对公司报送的向不特定对象发行可转换公司债券的申请文件进行了核对，认为申请文件齐备，决定予以受理。",
                    r"公司本次向不特定对象发行可转换公司债券事项尚需深交所审核，并经中国证券监督管理委员会（以下简称“中国证监会”）作出同意注册的决定后方可实施。",
                    r"公司本次向不特定对象发行可转换公司债券的事项最终能否通过深交所审核并获得中国证监会作出同意注册的批复及其时间尚存在不确定性。",
                ],
            )
        )

    if "权益分派" in title:
        return dedupe_points(
            regex_points(
                compact,
                [
                    r"向全体股东每10股派发现金人民币0\.78元（含税），不送红股、不以资本公积金转增股本。",
                    r"合计派发现金红利不超过36,894,098\.75元，合计派发现金红利总额占2025年归属于母公司股东的净利润为10\.07%。",
                    r"本次权益分派股权登记日为：2026年6月11日，除权除息日为：2026年6月12日。",
                    r"本次权益分派实施后，公司2022年限制性股票激励计划的限制性股票授予价格及授予数量、2023年限制性股票激励计划的限制性股票授予价格及授予数量、2026年限制性股票激励计划的限制性股票授予价格及授予数量将进行调整。",
                ],
            )
        )

    if "限制性股票" in title and "授予" in title:
        points = regex_points(
            compact,
            [
                r"限制性股票授予日：2026年5月20日",
                r"限制性股票授予数量：300\.00万股，约占本激励计划草案公告日公司股本总额47,300\.1266万股的0\.63%",
                r"限制性股票授予价格：11\.70元/股",
                r"本激励计划授予的激励对象共计68人[^。]*。",
                r"调整后，本激励计划的激励对象人数由69人调整为68人，授予的第二类限制性股票数量由304\.00万股调整为300\.00万股。",
                r"以2026年5月20日为授予日，向符合授予条件的68名激励对象授予限制性股票合计300\.00万股，授予价格均为11\.70元/股。",
            ],
        )
        return dedupe_points(points)

    return []


def announcement_key_points(title: str, columns: str, full_text: str) -> list[str]:
    if not full_text:
        return [columns or "公告原文暂未能提取，请打开原文核对。"]

    special_points = specialized_announcement_points(title, full_text)
    if special_points:
        return special_points

    section_match = re.search(
        r"(重大事项提示|重要内容提示|特别提示|风险提示|一、|一、本次|一、本报告期)(.*?)(特此公告|浙江松原汽车安全系统股份有限公司|董事会|$)",
        full_text,
        re.S,
    )
    focus_text = section_match.group(0) if section_match else full_text[:6000]
    keywords = [
        "受理",
        "审核",
        "注册",
        "可转换公司债券",
        "可转债",
        "募集资金",
        "监管",
        "处罚",
        "整改",
        "问询",
        "风险",
        "不确定性",
        "净利润",
        "现金流",
        "分红",
        "权益分派",
        "股权激励",
        "限制性股票",
        "回购",
        "减持",
        "质押",
    ]
    title_terms = [term for term in keywords if term in title]
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, sentence in enumerate(split_key_sentences(focus_text)):
        if sentence in seen:
            continue
        seen.add(sentence)
        score = 0
        score += sum(8 for term in keywords if term in sentence)
        score += sum(10 for term in title_terms if term in sentence)
        if re.search(r"\d", sentence):
            score += 5
        if any(word in sentence for word in ["尚需", "决定", "不存在", "不存在未披露", "注意投资风险", "真实、准确、完整"]):
            score += 4
        if any(word in sentence for word in ["目录", "释义", "声明", "备查文件", "咨询机构", "公告编号"]):
            score -= 12
        if len(sentence) > 120:
            score -= 3
        candidates.append((score, -idx, sentence))

    ranked = [item[2] for item in sorted(candidates, reverse=True) if item[0] > 0]
    if not ranked:
        ranked = split_key_sentences(focus_text)
    return ranked[:5] or [columns or "公告原文已读取，但未抽取到明确关键点。"]


def collect_records(config: dict) -> list[dict]:
    stock = config["stock"]
    keywords = config["keywords"]
    records: list[dict] = []

    ann = fetch_json(
        config["sources"]["announcements"]["url"],
        {
            "cb": "",
            "sr": "-1",
            "page_size": "30",
            "page_index": "1",
            "ann_type": "A",
            "client_source": "web",
            "stock_list": stock["code"],
        },
    )
    for index, row in enumerate(ann.get("data", {}).get("list", [])):
        title = row.get("title_ch") or row.get("title") or ""
        columns = "、".join(c.get("column_name", "") for c in row.get("columns", []))
        art_code = row.get("art_code", "")
        full_text = read_announcement_text(art_code) if index < MAX_ANNOUNCEMENTS_WITH_FULLTEXT else ""
        key_points = announcement_key_points(title, columns, full_text)
        score, tags, tone = score_item(title, columns, "公告", keywords)
        records.append(
            {
                "type": "公告",
                "title": title,
                "date": (row.get("display_time") or row.get("notice_date") or "")[:16],
                "source": "公司公告 / 东方财富",
                "url": pdf_url(art_code),
                "summary": "；".join(key_points[:2]),
                "keyPoints": key_points,
                "analysis": explain(title, full_text or columns),
                "tags": tags,
                "impact": score,
                "authority": 100,
                "tone": tone,
            }
        )

    param = {
        "uid": "",
        "keyword": f"{stock['shortName']} {stock['code']}",
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": 25,
                "preTag": "",
                "postTag": "",
            }
        },
    }
    news = fetch_json(config["sources"]["news"]["url"], {"cb": "", "param": json.dumps(param, ensure_ascii=False)})
    for row in news.get("result", {}).get("cmsArticleWebOld", []):
        title = row.get("title", "")
        content = row.get("content", "")
        score, tags, tone = score_item(title, content, "新闻", keywords)
        records.append(
            {
                "type": "新闻",
                "title": title,
                "date": row.get("date", "")[:16],
                "source": f"{row.get('mediaName', '财经媒体')} / 东方财富",
                "url": row.get("url", ""),
                "summary": content[:180],
                "keyPoints": [],
                "analysis": explain(title, content),
                "tags": tags,
                "impact": min(score, 90),
                "authority": 72,
                "tone": tone,
            }
        )

    dedup: dict[str, dict] = {}
    for record in records:
        dedup.setdefault(record["title"], record)
    return sorted(dedup.values(), key=lambda x: (x["impact"], x["authority"], x["date"]), reverse=True)[:18]


def explain(title: str, content: str) -> str:
    text = title + " " + content
    if "可转债" in text or "再融资" in text or "募集说明书" in text:
        return "再融资事项对资本结构、产能扩张和潜在摊薄影响较大，需跟踪审核问询、募投回报和转股节奏。"
    if "现金" in text or "净利润" in text or "季报" in text or "年报" in text:
        return "财务数据需同时看利润和现金流质量，重点关注经营现金流、应收账款、存货和毛利率变化。"
    if "权益分派" in text or "分红" in text:
        return "分红体现股东回报，但对中长期价值的影响仍取决于盈利质量和增长持续性。"
    if "股权激励" in text or "限制性股票" in text:
        return "股权激励有助于绑定团队，但需核对考核目标、股份费用和解禁节奏。"
    if "市值管理" in text:
        return "市值管理表态偏正面，但需要后续经营绩效、分红或回购等具体行动验证。"
    return "作为辅助信息跟踪，需结合公告原文、财报和行业景气度判断实际投资影响。"


def collect_quote(config: dict) -> dict:
    try:
        data = fetch_json(
            config["sources"]["quote"]["url"],
            {
                "secid": config["stock"]["secid"],
                "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f84,f85,f116,f117,f162,f167,f170",
            },
        ).get("data", {})
        if data:
            return {
                "price": to_float(data.get("f43"), 100),
                "change": to_float(data.get("f170"), 100),
                "amount": to_float(data.get("f48"), 10000),
                "turnover": to_float(data.get("f50"), 100),
                "marketCap": to_float(data.get("f116"), 100000000),
                "floatCap": to_float(data.get("f117"), 100000000),
                "pe": to_float(data.get("f162"), 100),
                "pb": to_float(data.get("f167"), 100),
                "source": "东方财富行情",
            }
    except Exception as exc:
        print(f"Eastmoney quote fetch failed, trying Tencent quote: {exc}")

    try:
        text = fetch_text(
            "https://qt.gtimg.cn/q",
            {"q": f"sz{config['stock']['code']}"},
            "https://gu.qq.com/",
        )
        payload = text.split('"', 2)[1]
        fields = payload.split("~")
        return {
            "price": to_float(fields[3]),
            "change": to_float(fields[32]),
            "amount": to_float(fields[37]),
            "turnover": to_float(fields[38]),
            "marketCap": to_float(fields[45]),
            "floatCap": to_float(fields[44]),
            "pe": to_float(fields[39]),
            "pb": to_float(fields[46]),
            "source": "腾讯行情",
        }
    except Exception as exc:
        print(f"Tencent quote fetch failed, continuing without quote data: {exc}")

    return {
        "price": None,
        "change": None,
        "amount": None,
        "turnover": None,
        "marketCap": None,
        "floatCap": None,
        "pe": None,
        "pb": None,
        "source": "行情暂不可用",
    }


def render(config: dict, quote: dict, records: list[dict]) -> str:
    generated_at = dt.datetime.now(BEIJING_TZ)
    today = generated_at.strftime("%Y-%m-%d")
    now = generated_at.strftime("%Y-%m-%d %H:%M")
    records_json = json.dumps(records, ensure_ascii=False)
    def fmt(value: float | None, unit: str = "") -> str:
        if value is None:
            return "暂无"
        return f"{value:.2f}{unit}"

    change_class = "red" if (quote["change"] or 0) >= 0 else "green"
    quote_source = html.escape(quote.get("source", "行情来源"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{config['stock']['shortName']} {config['stock']['code']} 每日信息看板</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif; background: #f6f7f9; color: #172033; }}
    header {{ background: #111827; color: #fff; padding: 28px 20px 20px; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    .sub {{ color: #cbd5e1; line-height: 1.6; }}
    .update-badge {{ display: inline-flex; align-items: center; gap: 8px; margin-top: 14px; padding: 9px 12px; border-radius: 7px; background: #dcfce7; color: #0f6b3d; font-weight: 700; }}
    .update-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #16a34a; }}
    main {{ padding: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: -34px; }}
    .card, .panel, article {{ background: white; border: 1px solid #d9dee8; border-radius: 8px; box-shadow: 0 10px 30px rgba(24,32,54,.08); }}
    .card {{ padding: 16px; min-height: 106px; }}
    .card label {{ display: block; color: #667085; font-size: 12px; margin-bottom: 8px; }}
    .card strong {{ font-size: 24px; }}
    .layout {{ display: grid; grid-template-columns: 300px 1fr; gap: 16px; margin-top: 16px; align-items: start; }}
    .panel {{ padding: 16px; }}
    .controls {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }}
    button, select {{ min-height: 38px; border: 1px solid #d9dee8; background: white; border-radius: 7px; padding: 0 10px; cursor: pointer; }}
    button.active {{ background: #275efe; color: white; }}
    .notice {{ margin: 0 0 12px; padding: 10px 12px; border: 1px solid #d9dee8; border-radius: 7px; background: #f8fafc; color: #344054; line-height: 1.6; }}
    .notice.has-today {{ border-color: #bbf7d0; background: #f0fdf4; color: #0f8a52; font-weight: 700; }}
    #items {{ display: grid; gap: 12px; }}
    article {{ padding: 16px; box-shadow: none; }}
    article.today {{ border-color: #37b26c; background: #f3fbf6; }}
    article.today, article.today h3 a, article.today p, article.today .keypoints, article.today .keypoints li {{ color: #0f8a52; }}
    article h3 {{ margin: 0; font-size: 17px; line-height: 1.4; }}
    article p {{ color: #344054; line-height: 1.7; }}
    .keypoints {{ margin: 12px 0; padding: 12px 14px; background: #f8fafc; border: 1px solid #e5e9f2; border-radius: 7px; color: #172033; }}
    .keypoints b {{ display: block; margin-bottom: 8px; }}
    .keypoints ul {{ margin: 0; padding-left: 20px; }}
    .keypoints li {{ margin: 6px 0; line-height: 1.65; }}
    a {{ color: #275efe; text-decoration: none; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; color: #667085; }}
    .tag {{ border-radius: 999px; padding: 4px 8px; background: #eef2f7; }}
    .tag.today-tag {{ background: #dcfce7; color: #0f8a52; font-weight: 700; }}
    .red {{ color: #c7352e; }} .green {{ color: #0f8a52; }} .amber {{ color: #b7791f; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} .layout {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 560px) {{ .grid {{ grid-template-columns: 1fr; margin-top: -20px; }} h1 {{ font-size: 24px; }} }}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>{config['stock']['shortName']} {config['stock']['code']} 每日信息看板</h1><div class="sub">{config['stock']['fullName']} | 北京时间 | 非投资建议</div><div class="update-badge"><span class="update-dot"></span>今日已更新：{now}</div></div></header>
  <main><div class="wrap">
    <section class="grid">
      <div class="card"><label>最新价</label><strong>{fmt(quote['price'], " 元")}</strong><p class="{change_class}">涨跌幅 {fmt(quote['change'], "%")}</p></div>
      <div class="card"><label>成交</label><strong>{fmt(quote['amount'], " 万元")}</strong><p>换手约 {fmt(quote['turnover'], "%")} | {quote_source}</p></div>
      <div class="card"><label>市值</label><strong>{fmt(quote['marketCap'], " 亿元")}</strong><p>流通市值 {fmt(quote['floatCap'], " 亿元")}</p></div>
      <div class="card"><label>估值</label><strong>PE {fmt(quote['pe'])}</strong><p>PB {fmt(quote['pb'])}</p></div>
    </section>
    <section class="layout">
      <aside class="panel"><h2>跟踪重点</h2><p>优先关注再融资审核进度、募投项目回报、经营现金流、毛利率、客户订单和回款节奏。公告权威性高于新闻，概念行情仅作情绪参考。</p><h2>风险预判</h2><p>若出现现金流持续为负、再融资问询集中于募投合理性、主要客户需求不及预期或行业价格竞争加剧，应提高风险权重。</p></aside>
      <section class="panel"><div class="controls"><button class="active" data-filter="all">全部</button><button data-filter="公告">公告</button><button data-filter="新闻">新闻</button><button data-filter="高影响">高影响</button><button data-filter="风险">风险</button><button data-filter="利好">利好</button><select id="sorter"><option value="priority">新增优先，按影响排序</option><option value="date">新增优先，按时间排序</option><option value="authority">新增优先，按权威性排序</option></select></div><div id="dailyNotice"></div><div id="items"></div></section>
    </section>
  </div></main>
  <script>
    const records = {records_json};
    const reportDate = "{today}";
    const dailyNoticeEl = document.querySelector("#dailyNotice");
    const itemsEl = document.querySelector("#items");
    const buttons = [...document.querySelectorAll("button[data-filter]")];
    const sorter = document.querySelector("#sorter");
    let activeFilter = "all";
    function isTodayRecord(i) {{
      return (i.date || "").slice(0, 10) === reportDate;
    }}
    function compareRecords(a, b) {{
      const todayDiff = Number(isTodayRecord(b)) - Number(isTodayRecord(a));
      if (todayDiff !== 0) return todayDiff;
      if (sorter.value === "date") return new Date(b.date.replace(" ","T")) - new Date(a.date.replace(" ","T"));
      if (sorter.value === "authority") return b.authority - a.authority || b.impact - a.impact;
      return b.impact - a.impact || b.authority - a.authority;
    }}
    function render() {{
      const shown = records.filter(i => activeFilter === "all" || i.type === activeFilter || i.tags.includes(activeFilter)).sort(compareRecords);
      const todayCount = shown.filter(isTodayRecord).length;
      dailyNoticeEl.className = todayCount ? "notice has-today" : "notice";
      dailyNoticeEl.textContent = todayCount ? `今日新增 ${{todayCount}} 条，已按影响度优先展示。` : "今日暂无新增公告或新闻。";
      itemsEl.innerHTML = shown.map(i => {{
        const isToday = isTodayRecord(i);
        const keyPoints = i.keyPoints && i.keyPoints.length ? `<div class="keypoints"><b>原文关键点</b><ul>${{i.keyPoints.map(p => `<li>${{p}}</li>`).join("")}}</ul></div>` : `<p>${{i.summary}}</p>`;
        const todayTag = isToday ? `<span class="tag today-tag">今日新增</span>` : "";
        return `<article class="${{isToday ? "today" : ""}}"><h3><a href="${{i.url}}" target="_blank" rel="noopener noreferrer">${{i.title}}</a></h3>${{keyPoints}}<p><b>投资解读：</b>${{i.analysis}}</p><div class="meta">${{todayTag}}<span class="tag">${{i.date}}</span><span class="tag">${{i.source}}</span>${{i.tags.map(t => `<span class="tag">${{t}}</span>`).join("")}}<span class="tag">影响分 ${{i.impact}}</span></div></article>`;
      }}).join("") || "<p>当前筛选没有结果。</p>";
    }}
    buttons.forEach(b => b.onclick = () => {{ buttons.forEach(x => x.classList.remove("active")); b.classList.add("active"); activeFilter = b.dataset.filter; render(); }});
    sorter.onchange = render;
    render();
  </script>
</body>
</html>"""


def main() -> None:
    config = json.loads(SOURCES.read_text(encoding="utf-8"))
    records = collect_records(config)
    quote = collect_quote(config)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html_text = render(config, quote, records)
    OUTPUT.write_text(html_text, encoding="utf-8")
    INDEX_OUTPUT.write_text(html_text, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {INDEX_OUTPUT}")


if __name__ == "__main__":
    main()
