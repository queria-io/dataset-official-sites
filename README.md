# 公式サイト

都道府県・市区町村・政令指定都市の区の公式サイトの URL を持つデータセットです。毎月サイトを開いて、ページのタイトルに団体名を含むことを確認し、確認した日と URL の変更履歴を残します。法人番号と全国地方公共団体コードで、ほかのデータセットと結合できます。

## テーブル

| テーブル | 内容 |
| --- | --- |
| `main.official_site` | 公式サイトの URL。1 行が 1 団体 |
| `main.official_site_history` | URL の変更履歴。1 行が 1 回の変更 |

## 使い方

茨城県の市町村の公式サイトを、確認した日と並べる:

```sql
SELECT lg_code, name, url, verified_at
FROM official_sites.main.official_site
WHERE prefecture_name = '茨城県' AND organization_type = 'municipality'
ORDER BY lg_code;
```

法人番号で houjin_bangou と結合する:

```sql
SELECT h.name, h.city_name, s.url
FROM official_sites.main.official_site s
JOIN houjin_bangou.main.mart_houjin_bangou h USING (corporate_number);
```

## 確認の方法

`tools/check.py` が `data/official_site.csv` の URL をすべて開きます。

- HTTP 200 で、ページのタイトルに団体名（`title_keyword` があればその文字列）を含めば、確認できたとして `verified_at` をその日にします
- 確認できて、開いた URL が別の URL にリダイレクトされていれば、移った先の URL に替えます。元の URL は `data/official_site_history.csv` に残します
- 開けない・タイトルが合わないときは、`url` と `verified_at` を前回のままにします。`checked_at`・`http_status`・`page_title` にそのときの結果を書きます

確認できない行は人が見て、`data/official_site.csv` を直します。タイトルに団体名を含まないサイト（「都庁総合ホームページ」など）は、`title_keyword` にタイトルに含まれる文字列を書きます。

GitHub Actions の Check が毎月 1 日に `tools/check.py` を流し、変わった分をプルリクエストにします。マージすると Sync がデータセットを作り直します。

## 作り方と注意

- 団体の一覧は「統計に用いる標準地域コード」（総務省統計局）の都道府県・市区町村・政令指定都市の区です。郡と支庁、役場の無い北方領土の 6 村は含めません
- 法人番号は「法人番号公表サイト」（国税庁）の法人種別 201（地方公共団体）を、都道府県名と団体名で突き合わせて付けています。政令指定都市の区は法人ではないので NULL です
- `verified_at` が古い行は、サイトが確認できない状態が続いています。URL が変わった可能性があります
- サイトによっては、アクセス元によって接続を拒否します（HTTP 403・408 など）。その行は `http_status` に結果が残ります

## ビルド

```bash
uv sync
uv run python tools/check.py   # サイトを開いて data/ を書き換える
scripts/build.sh               # dbt で作って fdl commit
```
