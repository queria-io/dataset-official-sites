{# 確認の記録 (site_check) と対象の一覧 (organization) をやめた後始末。
   モデルファイルを消しても DuckLake 側のテーブルは残るので、公開中のバージョンから落とす。
   DROP はデータベース名まで修飾する (既定のデータベースは :memory:)。
   本番の Sync が 1 回通ったら、この macro と dbt_project.yml の on-run-start をまとめて消してよい #}
{% macro drop_retired_tables() %}
  {% if not execute %}{{ return('') }}{% endif %}
  {% set found = run_query(
      "SELECT table_name FROM duckdb_tables()"
      ~ " WHERE database_name = 'official_sites' AND schema_name = 'main'"
      ~ "   AND table_name IN ('site_check', 'organization')"
  ) %}
  {% for row in found.rows %}
    {% do log('dropping retired table official_sites.main.' ~ row[0], info=True) %}
    {% do run_query('DROP TABLE official_sites.main."' ~ row[0] ~ '"') %}
  {% endfor %}
{% endmacro %}
