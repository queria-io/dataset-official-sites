{# 法人・団体ごとの今の公式サイト。main.py (巡回) と record.py (人の記録) が、公開中のバージョンを上書きして
   build/official_site.csv に書く #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    organization_type,
    nullif(prefecture_name, '') as prefecture_name,
    nullif(url, '') as url,
    nullif(url_source, '') as url_source,
    nullif(recorded_by, '') as recorded_by,
    nullif(note, '') as note,
    cast(nullif(verified_at, '') as timestamptz) as verified_at,
    cast(nullif(last_checked_at, '') as timestamptz) as last_checked_at,
    cast(nullif(last_http_status, '') as integer) as last_http_status,
    nullif(last_page_title, '') as last_page_title
from read_csv('build/official_site.csv', all_varchar = true)
