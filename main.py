"""公式サイトのテーブルを作る。

正本は確認の記録 (site_check) で、1 行が「ある日にある URL を開いた結果」。毎回の実行で追記し、
official_site と official_site_history は dbt がこの記録から SQL で作る。

1. 公開中のバージョンから、これまでの site_check を読む
2. 対象の法人・団体を出す (pipelines/organizations.py)
3. 開く URL を決める。overrides.csv に URL があればそれ、なければ最後に確認できた URL (リダイレクトの先)。
   確認できたことが無い対象は、候補の一覧から探す
4. 開いて確認し (pipelines/sites.py)、結果を site_check に追記して build/ に書く
5. dbt でテーブルを作る

前回のバージョンに site_check が無いとき (最初の 1 回) は、記録なしから作る。
前回のバージョンが読めないときは止まる (記録を失わないため)。
"""

import csv
import logging
from datetime import date
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
OVERRIDES = Path("overrides.csv")
ORG_FIELDS = ["corporate_number", "lg_code", "name", "organization_type", "prefecture_name"]
CHECK_FIELDS = [
    "corporate_number",
    "lg_code",
    "name",
    "url",
    "url_source",
    "checked_at",
    "final_url",
    "http_status",
    "page_title",
    "verified",
]


def connect():
    con = duckdb.connect()
    con.execute("install ducklake; load ducklake; install httpfs; load httpfs")
    for name in ("e_stat", "houjin_bangou", "official_sites"):
        con.execute(f"attach 'ducklake:{DATA}/{name}/ducklake.duckdb' as {name} (read_only)")
    return con


def text(v) -> str:
    return "" if v is None else str(v)


def previous_checks(con) -> list[dict]:
    exists = con.execute(
        "select count(*) from duckdb_tables() where database_name = 'official_sites' and table_name = 'site_check'"
    ).fetchone()[0]
    if not exists:
        return []
    cur = con.execute("select * from official_sites.main.site_check")
    cols = [d[0] for d in cur.description]
    return [{c: text(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def last_verified(checks: list[dict]) -> dict[str, str]:
    """対象ごとに、最後に確認できた URL (リダイレクトの先)。"""
    ok = sorted((c for c in checks if c["verified"] == "True"), key=lambda c: c["checked_at"])
    return {key(c): c["final_url"] for c in ok}


def targets(org: dict, override: dict, verified: dict[str, str], cands: dict[str, list[str]]) -> list[tuple[str, str]]:
    """開く URL とその出どころの組。"""
    if override.get("url"):
        return [(override["url"], "override")]
    if key(org) in verified:
        return [(verified[key(org)], "previous")]
    return [(u, "candidate") for u in cands.get(key(org), [])]


def check(org: dict, url: str, source: str, page: dict, override: dict, today: str) -> dict:
    row = {**org, "title_keyword": override.get("title_keyword", "")}
    return {
        **{f: text(org.get(f)) for f in ("corporate_number", "lg_code", "name")},
        "url": url,
        "url_source": source,
        "checked_at": today,
        **page,
        "verified": str(is_verified(row, page)),
    }


def build() -> None:
    today = date.today().isoformat()
    con = connect()
    overrides = {key(o): o for o in read_csv(OVERRIDES)}
    prev = previous_checks(con)
    verified = last_verified(prev)
    orgs = [o for o in organizations(con) if not overrides.get(key(o), {}).get("exclude")]
    cands = candidates([o for o in orgs if key(o) not in verified and not overrides.get(key(o), {}).get("url")])
    plan = [(o, url, source) for o in orgs for url, source in targets(o, overrides.get(key(o), {}), verified, cands)]
    pages = fetch_all([url for _, url, _ in plan])
    new = [check(o, url, source, pages[url], overrides.get(key(o), {}), today) for o, url, source in plan]
    write_csv(BUILD / "organization.csv", ORG_FIELDS, [{f: text(o.get(f)) for f in ORG_FIELDS} for o in orgs])
    write_csv(BUILD / "site_check.csv", CHECK_FIELDS, prev + new)
    ok = {key(c) for c in new if c["verified"] == "True"}
    log.info("%d 件の対象、%d 件の URL を開いた、確認できた対象 %d 件", len(orgs), len(new), len(ok))


def main():
    build()
    dbt = dbtRunner()
    for args in (["deps"], ["build"], ["docs", "generate"]):
        if not dbt.invoke(args).success:
            raise SystemExit(f"dbt {args[0]} failed")


if __name__ == "__main__":
    main()
