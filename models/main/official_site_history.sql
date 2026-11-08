{# 公式サイトの URL の変更履歴 (data/official_site_history.csv)。1 行が 1 回の変更 #}

select
    nullif(corporate_number, '') as corporate_number,
    nullif(lg_code, '') as lg_code,
    name,
    url,
    next_url,
    cast(changed_at as date) as changed_at
from read_csv(
    'data/official_site_history.csv',
    header = true,
    columns = {
        'corporate_number': 'varchar', 'lg_code': 'varchar', 'name': 'varchar',
        'url': 'varchar', 'next_url': 'varchar', 'changed_at': 'varchar'
    }
)
