{# 公式サイトの URL の変更と人の記録（build/official_site_history.csv、main.py と record.py が書く）。取得したままの形 #}

select *
from read_csv('build/official_site_history.csv', all_varchar = true)
