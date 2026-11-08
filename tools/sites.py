"""公式サイトの一覧の読み書きと、サイトを開いて確認する処理。"""

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "data" / "official_site.csv"
HISTORY = ROOT / "data" / "official_site_history.csv"

SITE_FIELDS = [
    "corporate_number",
    "lg_code",
    "name",
    "organization_type",
    "prefecture_name",
    "url",
    "title_keyword",
    "verified_at",
    "checked_at",
    "http_status",
    "page_title",
]
HISTORY_FIELDS = ["corporate_number", "lg_code", "name", "url", "next_url", "changed_at"]

USER_AGENT = "Mozilla/5.0 (compatible; queria-official-sites; +https://github.com/queria-io/dataset-official-sites)"
TITLE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
CHARSET = re.compile(rb"charset=[\"']?([\w-]+)", re.I)
SJIS = {"shift_jis", "shift-jis", "sjis", "x-sjis", "windows-31j"}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".part")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)
    tmp.replace(path)


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


def fetch(url: str, attempts: int = 3) -> dict:
    """開けない・408・5xx のときは間を空けて開き直す。"""
    page = fetch_once(url)
    for i in range(1, attempts):
        if page["http_status"] not in ("", "408") and not page["http_status"].startswith("5"):
            break
        time.sleep(5 * i)
        page = fetch_once(url)
    return page


def fetch_once(url: str, timeout: int = 30) -> dict:
    """URL を開き、リダイレクトの後の URL・ステータス・タイトルを返す。開けないときはステータスが空。"""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as r:
            body = r.read(1 << 20)
            return {
                "final_url": re.sub(r"^(https://[^/]+):443(?=/|$)|^(http://[^/]+):80(?=/|$)", r"\1\2", r.geturl()),
                "http_status": str(r.status),
                "page_title": page_title(body, r.headers.get("Content-Type", "")),
            }
    except HTTPError as e:
        return {"final_url": url, "http_status": str(e.code), "page_title": ""}
    except Exception:  # 名前解決・接続・TLS・タイムアウトはまとめて「開けない」とする
        return {"final_url": url, "http_status": "", "page_title": ""}


def is_verified(row: dict, page: dict) -> bool:
    """開けて、タイトルに団体名 (title_keyword があればそれ) を含むとき確認できたとする。"""
    keyword = row.get("title_keyword") or row["name"]
    return page["http_status"] == "200" and keyword in page["page_title"]


def checked(row: dict, page: dict, today: str) -> tuple[dict, dict | None]:
    """確認の結果を行に写す。確認できて URL が変わっていれば、新しい URL にして履歴の行も返す。"""
    ok = is_verified(row, page)
    moved = ok and page["final_url"].rstrip("/") != row["url"].rstrip("/")
    new = {
        **row,
        "url": page["final_url"] if moved else row["url"],
        "verified_at": today if ok else row.get("verified_at", ""),
        "checked_at": today,
        "http_status": page["http_status"],
        "page_title": page["page_title"],
    }
    history = (
        {
            "corporate_number": row["corporate_number"],
            "lg_code": row["lg_code"],
            "name": row["name"],
            "url": row["url"],
            "next_url": page["final_url"],
            "changed_at": today,
        }
        if moved
        else None
    )
    return new, history


def fetch_all(urls: list[str], workers: int = 8) -> list[dict]:
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fetch, urls))
