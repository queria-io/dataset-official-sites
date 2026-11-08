"""data/official_site.csv の最初の一覧を作る。一度だけ流す。

対象は都道府県・市区町村・政令指定都市の区。団体の一覧は Queria の e_stat (標準地域コード) と
houjin_bangou (法人番号) から作る。URL の候補は Wikidata の公式サイト (P856) を
全国地方公共団体コード (P429) で引く。候補をすべて開き、タイトルに団体名を含むものを選ぶ。
選べなかった団体は、候補の 1 つを確認できなかった行として残す。

uv run --group dev python tools/seed.py
"""

import csv
import io
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sites import HISTORY, HISTORY_FIELDS, SITE_FIELDS, SITES, USER_AGENT, checked, fetch_all, is_verified, write_csv

DATA = "https://data.queria.io/datasets/queria"

ORGANIZATIONS = """
with m as (
    select
        area_code || cast((11 - (6 * cast(area_code[1] as int) + 5 * cast(area_code[2] as int)
            + 4 * cast(area_code[3] as int) + 3 * cast(area_code[4] as int)
            + 2 * cast(area_code[5] as int)) % 11) % 10 as varchar) as lg_code,
        pref_name as prefecture_name,
        case
            when is_prefecture then pref_name
            when area_kind = 'designated_city' then designated_city_name
            else municipality_name
        end as name,
        case
            when area_kind = 'municipality' and pref_name = '東京都' and municipality_name like '%区'
                then 'special_ward'
            else area_kind
        end as organization_type
    from e_stat.code.municipality
    where area_kind in ('prefecture', 'municipality', 'designated_city', 'ward')
        -- 北方領土の 6 村は役場が無い
        and area_code not between '01695' and '01700'
)
select coalesce(h.corporate_number, '') as corporate_number, m.*
from m
left join houjin_bangou.main.mart_houjin_bangou h
    -- 表記は「ヶ・ケ」「檮・梼」が揺れる
    on h.kind = '201' and h.prefecture_name = m.prefecture_name
    and translate(h.name, 'ケ檮', 'ヶ梼') = translate(m.name, 'ケ檮', 'ヶ梼')
    and m.organization_type <> 'ward'
-- 同じ名前の団体が同じ都道府県に複数あれば、所在地が自分の団体を選ぶ
-- (法人番号の所在地は、市町村なら自分、政令指定都市なら市役所のある区、都道府県なら県庁所在地)
qualify row_number() over (partition by m.lg_code order by h.lg_code = m.lg_code desc nulls last) = 1
order by m.lg_code
"""

CANDIDATES = """
SELECT ?code ?url WHERE {
  ?item wdt:P429 ?code ; wdt:P856 ?url .
}
"""


def organizations() -> list[dict]:
    con = duckdb.connect()
    con.execute("install ducklake; load ducklake; install httpfs; load httpfs")
    for name in ("e_stat", "houjin_bangou"):
        con.execute(f"attach 'ducklake:{DATA}/{name}/ducklake.duckdb' as {name} (read_only)")
    cur = con.execute(ORGANIZATIONS)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def candidates() -> dict[str, list[str]]:
    url = "https://query.wikidata.org/sparql?" + urlencode({"query": CANDIDATES})
    req = Request(url, headers={"Accept": "text/csv", "User-Agent": USER_AGENT})
    with urlopen(req, timeout=120) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode())))
    return {code: sorted({r["url"] for r in rows if r["code"] == code}) for code in {r["code"] for r in rows}}


def best(org: dict, urls: list[str], pages: dict[str, dict], today: str) -> dict:
    """確認できた候補を先に、その中では短い URL (トップページ) を選ぶ。"""
    row = {**org, "url": "", "title_keyword": "", "verified_at": "", "checked_at": "", "http_status": "", "page_title": ""}
    ranked = sorted(urls, key=lambda u: (not is_verified(row, pages[u]), len(pages[u]["final_url"])))
    return checked({**row, "url": ranked[0]}, pages[ranked[0]], today)[0] if ranked else row


def main() -> None:
    today = date.today().isoformat()
    orgs = organizations()
    cands = candidates()
    urls = sorted({u for o in orgs for u in cands.get(o["lg_code"], [])})
    pages = dict(zip(urls, fetch_all(urls)))
    rows = [best(o, cands.get(o["lg_code"], []), pages, today) for o in orgs]
    write_csv(SITES, SITE_FIELDS, rows)
    write_csv(HISTORY, HISTORY_FIELDS, [])
    print(f"{len(rows)} 団体、確認できた {sum(r['verified_at'] == today for r in rows)} 団体")


if __name__ == "__main__":
    main()
