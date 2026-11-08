{# 公式サイトの確認の記録。1 行が「ある日にある URL を開いた結果」。
   main.py が公開中のバージョンの記録に今回の確認を足して build/site_check.csv に書く #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    url,
    url_source,
    cast(checked_at as date) as checked_at,
    final_url,
    cast(nullif(http_status, '') as integer) as http_status,
    nullif(page_title, '') as page_title,
    cast(verified as boolean) as verified
from read_csv('build/site_check.csv', all_varchar = true)
