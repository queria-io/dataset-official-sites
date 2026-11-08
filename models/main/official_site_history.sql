{# 公式サイトの URL の変更と、人の記録。main.py (巡回) と record.py (人の記録) が、公開中のバージョンに追記して
   build/official_site_history.csv に書く #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    event,
    nullif(url, '') as url,
    nullif(previous_url, '') as previous_url,
    nullif(recorded_by, '') as recorded_by,
    nullif(note, '') as note,
    cast(recorded_at as timestamptz) as recorded_at
from read_csv('build/official_site_history.csv', all_varchar = true)
