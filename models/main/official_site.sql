{# 法人・団体ごとの今の公式サイト。site_check から、最後に確認できた結果の到達先の URL を選ぶ。
   確認できたことが無ければ url と verified_at は NULL。最後に開いた結果は last_* の列 #}

with checks as (
    select *, coalesce(lg_code, corporate_number) as org_key
    from {{ ref('site_check') }}
),

verified as (
    select org_key, final_url as url, url_source, checked_at as verified_at
    from checks
    where verified
    qualify row_number() over (partition by org_key order by checked_at desc, url_source = 'override' desc, length(final_url)) = 1
),

latest as (
    select org_key, checked_at, http_status, page_title
    from checks
    qualify row_number() over (partition by org_key order by checked_at desc, verified desc, length(final_url)) = 1
)

select
    o.corporate_number,
    o.lg_code,
    o.name,
    o.organization_type,
    o.prefecture_name,
    v.url,
    v.url_source,
    v.verified_at,
    l.checked_at as last_checked_at,
    l.http_status as last_http_status,
    l.page_title as last_page_title
from {{ ref('organization') }} o
left join verified v on v.org_key = coalesce(o.lg_code, o.corporate_number)
left join latest l on l.org_key = coalesce(o.lg_code, o.corporate_number)
