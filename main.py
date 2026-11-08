"""公式サイトのテーブルを作る。

- official_site: 1 団体・機関 1 行の今の状態。毎回の実行で前回のバージョンを読み、上書きする
- official_site_history: URL が変わったときと、人が記録・除外したときに 1 行追記する

毎月の巡回 (このファイル) は次のように進む。

1. 公開中のバージョンから official_site と official_site_history を読む
2. 対象の法人・団体を出す (pipelines/organizations.py)。人が最後に exclude を記録した対象は外す
3. 開く URL を決める。人が最後に記録した URL (manual) があればそれ、なければ今の URL。
   URL が無い対象は、候補の一覧から探す
4. 開いて確認し (pipelines/sites.py)、確認できた到達先の URL が今の URL と違えば履歴に追記する
5. build/ に書き、dbt でテーブルを作る

前回のバージョンに今の形の official_site_history が無いとき (最初の 1 回) は、記録なしから作る。
前回のバージョンが読めないときは止まる (記録を失わないため)。
"""

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from dbt.cli.main import dbtRunner

from pipelines.organizations import candidates, key, organizations
from pipelines.sites import fetch_all, is_verified

# dbt を読み込むとルートロガーが先に設定されるので、force で上書きする
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
log = logging.getLogger(__name__)

DATA = "https://data.queria.io/datasets/queria"
BUILD = Path("build")
ORG_FIELDS = ["corporate_number", "lg_code", "name", "organization_type", "prefecture_name"]
SITE_FIELDS = ORG_FIELDS + [
    "url",
    "url_source",
    "recorded_by",
    "note",
    "verified_at",
    "last_checked_at",
    "last_http_status",
    "last_page_title",
]
EVENT_FIELDS = ["corporate_number", "lg_code", "name", "event", "url", "previous_url", "recorded_by", "note", "recorded_at"]
NO_PAGE = {"final_url": "", "http_status": "", "page_title": ""}


def connect():
    con = duckdb.connect()
    con.execute("install ducklake; load ducklake; install httpfs; load httpfs")
    for name in ("e_stat", "houjin_bangou", "official_sites"):
        con.execute(f"attach 'ducklake:{DATA}/{name}/ducklake.duckdb' as {name} (read_only)")
    return con


def text(v) -> str:
    return "" if v is None else str(v)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def published(con) -> tuple[dict[str, dict], list[dict]]:
    """公開中の official_site (キーごと) と official_site_history。今の形の履歴 (event 列) が無ければ、
    最初の 1 回としてどちらも空にする。"""
    exists = con.execute(
        "select count(*) from duckdb_columns() where database_name = 'official_sites' "
        "and table_name = 'official_site_history' and column_name = 'event'"
    ).fetchone()[0]
    if not exists:
        return {}, []

    def rows(table: str) -> list[dict]:
        cur = con.execute(f"select * from official_sites.main.{table}")
        cols = [d[0] for d in cur.description]
        return [{c: text(v) for c, v in zip(cols, r)} for r in cur.fetchall()]

    return {key(s): s for s in rows("official_site")}, rows("official_site_history")


def by_person(events: list[dict]) -> dict[str, dict]:
    """対象ごとに、人が最後に記録した行 (manual か exclude)。"""
    person = sorted((e for e in events if e["event"] in ("manual", "exclude")), key=lambda e: e["recorded_at"])
    return {key(e): e for e in person}


def active(orgs: list[dict], events: list[dict]) -> list[dict]:
    """人が最後に exclude を記録した対象を除く。"""
    person = by_person(events)
    return [o for o in orgs if person.get(key(o), {}).get("event") != "exclude"]


def org_fields(org: dict) -> dict:
    return {f: text(org.get(f)) for f in ORG_FIELDS}


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write(sites: list[dict], events: list[dict]) -> None:
    write_csv(BUILD / "official_site.csv", SITE_FIELDS, sites)
    write_csv(BUILD / "official_site_history.csv", EVENT_FIELDS, events)


def dbt_build() -> None:
    dbt = dbtRunner()
    for args in (["deps"], ["build"], ["docs", "generate"]):
        if not dbt.invoke(args).success:
            raise SystemExit(f"dbt {args[0]} failed")


def urls_to_open(org: dict, site: dict, pin: str, cands: dict[str, list[str]]) -> list[str]:
    return [pin] if pin else [site["url"]] if site.get("url") else cands.get(key(org), [])


def update(org: dict, site: dict, pin: dict, pages: list[dict], at: str) -> tuple[dict, list[dict]]:
    """開いた結果から、新しい official_site の行と、履歴に追記する行を作る。
    人が記録した URL (pin) は、HTTP 200 で開ければ確認できたとする。"""
    ok = sorted((p for p in pages if is_verified(org, p, trusted=bool(pin))), key=lambda p: len(p["final_url"]))
    shown = (ok or pages or [NO_PAGE])[0]
    row = {
        **{f: site.get(f, "") for f in SITE_FIELDS},
        **org_fields(org),
        "last_checked_at": at if pages else site.get("last_checked_at", ""),
        "last_http_status": shown["http_status"],
        "last_page_title": shown["page_title"],
    }
    if not ok:
        return row, []
    url = ok[0]["final_url"]
    row["verified_at"] = at
    if url == site.get("url"):
        return row, []
    source = "manual" if pin else "redirect" if site.get("url") else "candidate"
    row.update(url=url, url_source=source, **({} if pin else {"recorded_by": "", "note": ""}))
    event = {
        **org_fields(org),
        "event": "found" if not site.get("url") else "moved",
        "url": url,
        "previous_url": site.get("url", ""),
        "recorded_at": at,
    }
    return row, [event]


def crawl() -> None:
    at = now()
    con = connect()
    sites, events = published(con)
    orgs = active(organizations(con), events)
    pins = {k: e["url"] for k, e in by_person(events).items() if e["event"] == "manual"}
    cands = candidates([o for o in orgs if key(o) not in pins and not sites.get(key(o), {}).get("url")])
    plan = {key(o): urls_to_open(o, sites.get(key(o), {}), pins.get(key(o), ""), cands) for o in orgs}
    pages = fetch_all([u for urls in plan.values() for u in urls])
    results = [update(o, sites.get(key(o), {}), pins.get(key(o), ""), [pages[u] for u in plan[key(o)]], at) for o in orgs]
    new = [e for _, es in results for e in es]
    write([r for r, _ in results], events + new)
    verified = sum(r["verified_at"] == at for r, _ in results)
    log.info("%d 件の対象、%d 件の URL を開いた、確認できた対象 %d 件、URL の変更 %d 件", len(orgs), len(pages), verified, len(new))


def main():
    crawl()
    dbt_build()


if __name__ == "__main__":
    main()
