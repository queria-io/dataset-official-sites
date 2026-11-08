# 公式サイト

地方公共団体と国の機関の公式サイトの URL を持つデータセットです。毎月サイトを開いて、ページのタイトルに団体・機関の名前を含むことを確認し、その記録を残します。法人番号と全国地方公共団体コードで、ほかのデータセットと結合できます。

## テーブル

| テーブル | 内容 |
| --- | --- |
| `main.official_site` | 今の公式サイトの URL。1 行が 1 つの団体・機関。毎月の確認で上書きする |
| `main.official_site_history` | URL の変更と、人の記録。1 行が 1 回の変更か記録 |

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

毎月の巡回（`main.py`）は、公開中のバージョンの `official_site` と `official_site_history` を読み、次のように進みます。

1. 対象の団体・機関を、標準地域コード（`e_stat`）と法人番号（`houjin_bangou`）から作る。人が最後に対象から外した団体・機関は除く
2. 開く URL を決める。人が最後に記録した URL があればその URL、なければ今の URL。URL が無い団体・機関は、候補の URL をすべて開く
3. HTTP 200 でページのタイトルに名前を含めば、確認できたとする。人が記録した URL は、HTTP 200 で開ければ確認できたとする
4. `official_site` を上書きする。確認できた到達先の URL が今の URL と違えば、`official_site_history` に 1 行追記する

名前の照合では、名前のほかに「市」「町」などを除いた語幹（2 文字以上）と、よみがなの語幹（3 文字以上）も使います。「ヶ・ケ」「檮・梼」は同じ文字として扱います。政令指定都市の区は、ほかの団体と重なりやすいので名前だけで照合します。

URL の候補は次の一覧から取ります。

- 地方公共団体と府省庁・委員会・本部など: Wikidata の公式サイト（P856）を、全国地方公共団体コード（P429）か法人番号（P3225）で引いたもの
- 裁判所: 裁判所ウェブサイトの「各地の裁判所」
- 検察庁: 検察庁ウェブサイトの「各検察庁の紹介」

## 人が直すとき

確認できない団体・機関は、上の SQL で引いて見ます。サイトを確認したら、`record.py` で記録します。記録は `official_site_history` に、記録した人と理由とともに 1 行追記されます。対象は、地方公共団体なら全国地方公共団体コード、国の機関なら法人番号で指定します。

```bash
# URL を記録する。以後の巡回はこの URL を開く
scripts/build.sh python record.py 023817 https://www.town.itayanagi.aomori.jp/ --note "候補の URL が別の町のものだった"

# 対象から外す。後から URL を記録すると戻る
scripts/build.sh python record.py 1000011000005 --exclude --note "理由"
```

記録した人は `--by` で指定します。省くと git の `user.name` が入ります。`record.py` はサイトを巡回せず、記録を追記して `official_site` を作り直し、新しいバージョンとして公開します。

## ビルド

```bash
uv sync
scripts/build.sh   # サイトを開いて確認し、dbt で作って fdl commit
```

GitHub Actions の Sync が毎月 1 日と、main へのマージのたびに作り直します。サイトによっては、アクセス元によって接続を拒否します（HTTP 403・408 など）。その団体・機関は前回確認できた URL のまま残ります。
