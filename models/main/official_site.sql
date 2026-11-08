{# 公式サイトの一覧 (data/official_site.csv) を型付けする。1 行が 1 団体。
   一覧は tools/check.py が毎月サイトを開いて書き換える #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    organization_type,
    prefecture_name,
    nullif(url, '') as url,
    cast(nullif(verified_at, '') as date) as verified_at,
    cast(nullif(checked_at, '') as date) as checked_at,
    cast(nullif(http_status, '') as integer) as http_status,
    nullif(page_title, '') as page_title
from read_csv('data/official_site.csv', all_varchar = true)
