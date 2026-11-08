{# 公式サイトを持たせる対象 (main.py が e_stat と houjin_bangou から作る)。official_site の行の元 #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    organization_type,
    nullif(prefecture_name, '') as prefecture_name
from read_csv('build/organization.csv', all_varchar = true)
