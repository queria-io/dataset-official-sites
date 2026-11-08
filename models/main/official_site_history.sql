{# 公式サイトの URL の変更履歴。site_check の確認できた結果を日付順に並べ、到達先の URL が前回と変わった時点を 1 行にする #}

with verified as (
    select
        coalesce(lg_code, corporate_number) as org_key,
        corporate_number,
        lg_code,
        name,
        checked_at,
        final_url as url
    from {{ ref('site_check') }}
    where verified
    qualify row_number() over (
        partition by coalesce(lg_code, corporate_number), checked_at
        order by url_source = 'override' desc, length(final_url)
    ) = 1
),

changes as (
    select *, lag(url) over (partition by org_key order by checked_at) as previous_url
    from verified
)

select corporate_number, lg_code, name, previous_url as url, url as next_url, checked_at as changed_at
from changes
where previous_url is not null and previous_url <> url
