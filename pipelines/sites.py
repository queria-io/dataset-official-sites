"""公式サイトを開いて、到達した URL・ステータス・タイトルを取得し、確認の結果を行に写す。"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; queria-official-sites; +https://github.com/queria-io/dataset-official-sites)"
TITLE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
CHARSET = re.compile(rb"charset=[\"']?([\w-]+)", re.I)
SJIS = {"shift_jis", "shift-jis", "sjis", "x-sjis", "windows-31j"}
DEFAULT_PORT = re.compile(r"^(https://[^/]+):443(?=/|$)|^(http://[^/]+):80(?=/|$)")


def decode(body: bytes, enc: str) -> str:
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def encoding(body: bytes, content_type: str) -> str:
    m = CHARSET.search(content_type.encode()) or CHARSET.search(body[:16384])
    enc = m.group(1).decode().lower() if m else "utf-8"
    return "cp932" if enc in SJIS else enc


def page_title(body: bytes, content_type: str) -> str:
    m = TITLE.search(body)
    return re.sub(r"\s+", " ", decode(m.group(1), encoding(body, content_type))).strip()[:200] if m else ""


def fetch_once(url: str, timeout: int = 30) -> dict:
    """URL を開き、リダイレクトの後の URL・ステータス・タイトルを返す。開けないときはステータスが空。"""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as r:
            body = r.read(1 << 20)
            return {
                "final_url": DEFAULT_PORT.sub(r"\1\2", r.geturl()),
                "http_status": str(r.status),
                "page_title": page_title(body, r.headers.get("Content-Type", "")),
            }
    except HTTPError as e:
        return {"final_url": url, "http_status": str(e.code), "page_title": ""}
    except Exception:  # 名前解決・接続・TLS・タイムアウトはまとめて「開けない」とする
        return {"final_url": url, "http_status": "", "page_title": ""}


def fetch(url: str, attempts: int = 3) -> dict:
    """開けない・408・5xx のときは間を空けて開き直す。"""
    page = fetch_once(url)
    for i in range(1, attempts):
        if page["http_status"] not in ("", "408") and not page["http_status"].startswith("5"):
            break
        time.sleep(5 * i)
        page = fetch_once(url)
    return page


def fetch_all(urls: list[str], workers: int = 8) -> dict[str, dict]:
    unique = sorted(set(urls))
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(unique, ex.map(fetch, unique)))


VARIANTS = str.maketrans("ヶ檮", "ケ梼")
SUFFIX = re.compile(r"(都|道|府|県|市|町|村|区)$")
KANA_SUFFIX = re.compile(r"(けん|ふ|と|どう|し|ちょう|まち|そん|むら|く)$")


def keywords(row: dict) -> list[str]:
    """タイトルに含まれていれば確認できたとする文字列。名前、名前から「市」「町」などを除いた 2 文字以上の語幹、
    よみがなの語幹 (3 文字以上)。政令指定都市の区は「中央」「北」のように他の団体と重なるので、名前だけを使う。"""
    if row.get("organization_type") == "ward":
        return [row["name"]]
    stem = SUFFIX.sub("", row["name"])
    kana = KANA_SUFFIX.sub("", row.get("yomigana") or "")
    return [row["name"]] + [stem] * (len(stem) >= 2) + [kana] * (len(kana) >= 3)


def is_verified(row: dict, page: dict, trusted: bool = False) -> bool:
    """開けて、タイトルに keywords(row) のどれかを含むとき確認できたとする。表記の揺れ (ヶ・ケ、檮・梼) は同じに見る。
    trusted (人が確認した URL) なら、開けただけで確認できたとする。"""
    title = page["page_title"].translate(VARIANTS)
    return page["http_status"] == "200" and (trusted or any(k.translate(VARIANTS) in title for k in keywords(row)))
