"""公式サイトを持たせる対象と、URL の候補。

対象:
- 地方公共団体: 標準地域コード (e_stat) の都道府県・市区町村・政令指定都市の区。郡・支庁と、役場の無い北方領土の 6 村は含めない。
  法人番号は houjin_bangou の法人種別 201 を都道府県名と団体名で突き合わせて付ける
- 国の機関: houjin_bangou の法人種別 101。簡易裁判所（東京簡易裁判所を除く）と検察審査会は、
  地方裁判所のサイトの中にあるので含めない

URL の候補 (一覧に無い対象にだけ探す):
- 地方公共団体と府省庁・委員会・本部など: Wikidata の公式サイト (P856) を全国地方公共団体コード (P429) か法人番号 (P3225) で引く
- 裁判所: 裁判所ウェブサイトの「各地の裁判所」。地方裁判所と家庭裁判所は同じサイト
- 検察庁: 検察庁ウェブサイトの「各検察庁の紹介」
"""

import csv
import io
import re
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from pipelines.sites import USER_AGENT

LOCAL = """
with m as (
    select
        area_code || cast((11 - (6 * cast(area_code[1] as int) + 5 * cast(area_code[2] as int)
            + 4 * cast(area_code[3] as int) + 3 * cast(area_code[4] as int)
            + 2 * cast(area_code[5] as int)) % 11) % 10 as varchar) as lg_code,
        pref_name as prefecture_name,
        yomigana,
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
"""

NATIONAL = """
select
    corporate_number,
    '' as lg_code,
    prefecture_name,
    '' as yomigana,
    name,
    case
        when name like '%裁判所' then 'court'
        when name like '%検察庁' then 'public_prosecutors_office'
        else 'national_agency'
    end as organization_type
from houjin_bangou.main.mart_houjin_bangou
where kind = '101'
    and not (name like '%簡易裁判所' and name <> '東京簡易裁判所')
    and name not like '%検察審査会'
"""

COURTS = "https://www.courts.go.jp/courthouse/map/index.html"
PROSECUTORS = "https://www.kensatsu.go.jp/kakuchou/index.htm"
SUPREME_COURT = {"最高裁判所": "https://www.courts.go.jp/saikosai/index.html"}
ANCHOR = re.compile(r'href="([^"]+)"[^>]*>([^<]+)<')

WIKIDATA = """
SELECT ?key ?url WHERE {
  VALUES ?key { %s }
  ?item wdt:%s ?key ; wdt:P856 ?url .
}
"""


def organizations(con) -> list[dict]:
    """con には e_stat と houjin_bangou を ATTACH しておく。"""
    cur = con.execute(f"select * from ({LOCAL}) union all by name select * from ({NATIONAL}) order by all")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get(url: str) -> str:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def listed(page: str, pattern: str) -> dict[str, str]:
    """一覧のページのリンクから、文字が pattern に合う機関の名前と URL の組を作る。
    「札幌地方裁判所／札幌家庭裁判所／札幌地裁管内の簡易裁判所」は 2 つの機関に分ける。"""
    return {
        name: urljoin(page, href)
        for href, text in ANCHOR.findall(get(page))
        for name in re.split(r"[／/]", text.strip())
        if re.fullmatch(pattern, name)
    }


def wikidata(prop: str, keys: list[str]) -> dict[str, list[str]]:
    if not keys:
        return {}
    query = WIKIDATA % (" ".join(f'"{k}"' for k in keys), prop)
    req = Request(
        "https://query.wikidata.org/sparql",
        data=urlencode({"query": query}).encode(),
        headers={"Accept": "text/csv", "User-Agent": USER_AGENT},
    )
    with urlopen(req, timeout=120) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode())))
    return {k: sorted({r["url"] for r in rows if r["key"] == k}) for k in keys}


def candidates(orgs: list[dict]) -> dict[str, list[str]]:
    """対象ごとの URL の候補。キーは key(org)。"""
    if not orgs:
        return {}
    courts = [o for o in orgs if o["organization_type"] in ("court", "public_prosecutors_office")]
    by_name = (
        {
            **listed(COURTS, r"\S+(高等|地方|家庭|簡易)裁判所"),
            **listed(PROSECUTORS, r"\S+(高等|地方)検察庁|最高検察庁"),
            **SUPREME_COURT,
        }
        if courts
        else {}
    )
    local = wikidata("P429", [o["lg_code"] for o in orgs if o["lg_code"]])
    national = wikidata("P3225", [o["corporate_number"] for o in orgs if not o["lg_code"] and o["name"] not in by_name])
    return {
        key(o): [by_name[o["name"]]] if o["name"] in by_name else local.get(o["lg_code"]) or national.get(o["corporate_number"]) or []
        for o in orgs
    }


def key(row: dict) -> str:
    """地方公共団体は全国地方公共団体コード、国の機関は法人番号で 1 行を決める。"""
    return row.get("lg_code") or row["corporate_number"]
