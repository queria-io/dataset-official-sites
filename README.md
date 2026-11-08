# 公式サイト

地方公共団体と国の機関の公式サイトの URL を持つデータセットです。毎月サイトを開いて、ページのタイトルに団体・機関の名前を含むことを確認し、その記録を残します。法人番号と全国地方公共団体コードで、ほかのデータセットと結合できます。

## テーブル

| テーブル | 内容 |
| --- | --- |
| `main.official_site` | 今の公式サイトの URL。1 行が 1 つの団体・機関 |
| `main.official_site_history` | URL の変更履歴。1 行が 1 回の変更 |
| `main.site_check` | サイトを開いて確認した記録。1 行が「ある日にある URL を開いた結果」 |

対象は次のとおりです。

- 地方公共団体: 「統計に用いる標準地域コード」（総務省統計局）の都道府県・市区町村・政令指定都市の区。郡・支庁と、役場の無い北方領土の 6 村は含めません
- 国の機関: 「法人番号公表サイト」（国税庁）の法人種別 101（国の機関）。府省庁・委員会・本部など、裁判所、検察庁です。簡易裁判所（東京簡易裁判所を除く）と検察審査会は地方裁判所のサイトの中にあるので含めません

## 使い方

茨城県の市町村の公式サイトを、確認した日と並べる:

```sql
SELECT lg_code, name, url, verified_at
FROM official_sites.main.official_site
WHERE prefecture_name = '茨城県' AND organization_type = 'municipality'
ORDER BY lg_code;
```

確認できていない団体・機関を、最後に開いた結果と並べる:

```sql
SELECT name, url, verified_at, last_http_status, last_page_title
FROM official_sites.main.official_site
WHERE verified_at IS NULL OR verified_at < last_checked_at;
```

## 作り方

`site_check` が正本です。毎月の更新（`main.py`）で次のように追記し、`official_site` と `official_site_history` は dbt がこの記録から作ります。

1. 対象の団体・機関を、標準地域コード（`e_stat`）と法人番号（`houjin_bangou`）から作る
2. 開く URL を決める。`overrides.csv` に URL があればその URL、なければ前回確認できたときの到達先の URL。確認できたことが無い団体・機関は、候補の URL をすべて開く
3. 開いた結果を `site_check` に追記する。HTTP 200 でページのタイトルに名前を含めば、確認できたとする

名前の照合では、名前のほかに「市」「町」などを除いた語幹（2 文字以上）と、よみがなの語幹（3 文字以上）も使います。「ヶ・ケ」「檮・梼」は同じ文字として扱います。政令指定都市の区は、ほかの団体と重なりやすいので名前だけで照合します。

URL の候補は次の一覧から取ります。

- 地方公共団体と府省庁・委員会・本部など: Wikidata の公式サイト（P856）を、全国地方公共団体コード（P429）か法人番号（P3225）で引いたもの
- 裁判所: 裁判所ウェブサイトの「各地の裁判所」
- 検察庁: 検察庁ウェブサイトの「各検察庁の紹介」

## 人が直すとき

確認できない団体・機関は、上の SQL で引いて見ます。直すものがあれば `overrides.csv` に 1 行追加するプルリクエストを出します。

| 列 | 使い方 |
| --- | --- |
| `corporate_number` / `lg_code` | 対象。地方公共団体は `lg_code`、国の機関は `corporate_number` |
| `url` | 開く URL を指定する。候補が誤っているときや、候補が無いとき |
| `title_keyword` | タイトルの照合に使う文字列。タイトルに名前を含まないサイト（「都庁総合ホームページ」など） |
| `exclude` | 何か書くと対象から外す |
| `note` | 直した理由 |

`url` を指定した行は、毎回その URL を開きます。サイトが移ってリダイレクトされれば、到達先の URL が `official_site` に入ります。

## ビルド

```bash
uv sync
scripts/build.sh   # サイトを開いて確認し、dbt で作って fdl commit
```

GitHub Actions の Sync が毎月 1 日と、main へのマージのたびに作り直します。サイトによっては、アクセス元によって接続を拒否します（HTTP 403・408 など）。その団体・機関は前回確認できた URL のまま残ります。
