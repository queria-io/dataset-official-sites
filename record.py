"""人が確認した URL か、対象から外すことを記録し、テーブルを作り直す。サイトの巡回はしない。

    scripts/build.sh python record.py 023817 https://www.town.itayanagi.aomori.jp/ --note "候補の URL が別の町のものだった"
    scripts/build.sh python record.py 1000011000005 --exclude --note "理由"

対象は全国地方公共団体コード (地方公共団体) か法人番号 (国の機関)。記録は official_site_history に 1 行追記する。
URL を記録すると official_site の URL をその URL にし、以後の巡回はその URL を開いて HTTP 200 なら確認できたとする。
--exclude を記録すると official_site から外す。もう一度 URL を記録すれば戻る。
記録した人は --by (省略すると git の user.name)。
"""

import argparse
import subprocess

from main import active, connect, dbt_build, now, org_fields, published, write
from pipelines.organizations import key, organizations
from pipelines.sites import fetch


def git_user() -> str:
    return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("target", help="全国地方公共団体コード (6 桁) か法人番号 (13 桁)")
    p.add_argument("url", nargs="?", default="")
    p.add_argument("--exclude", action="store_true", help="対象から外す")
    p.add_argument("--note", required=True, help="記録した理由")
    p.add_argument("--by", default=git_user(), help="記録した人")
    a = p.parse_args()
    if bool(a.url) == a.exclude:
        p.error("URL か --exclude のどちらか 1 つを指定する")
    if not a.by:
        p.error("--by を指定する")
    at = now()
    con = connect()
    sites, events = published(con)
    orgs = organizations(con)
    org = next((o for o in orgs if key(o) == a.target), None)
    if org is None:
        p.error(f"{a.target} は対象にない")
    site = sites.get(a.target, {})
    event = {
        **org_fields(org),
        "event": "exclude" if a.exclude else "manual",
        "url": a.url,
        "previous_url": site.get("url", ""),
        "recorded_by": a.by,
        "note": a.note,
        "recorded_at": at,
    }
    page = fetch(a.url) if a.url else {}
    recorded = {
        **site,
        **org_fields(org),
        "url": a.url,
        "url_source": "manual",
        "recorded_by": a.by,
        "note": a.note,
        "verified_at": at,
        "last_checked_at": at,
        "last_http_status": page.get("http_status", ""),
        "last_page_title": page.get("page_title", ""),
    }
    rows = {**sites, a.target: recorded}
    events = events + [event]
    write([rows.get(key(o)) or org_fields(o) for o in active(orgs, events)], events)
    dbt_build()


if __name__ == "__main__":
    main()
