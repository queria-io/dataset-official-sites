{# 法人・団体ごとの今の公式サイト（build/official_site.csv、main.py と record.py が書く）。取得したままの形 #}

select *
from read_csv('build/official_site.csv', all_varchar = true)
