# dataset-official-sites

Queria のデータセット `official_sites`（公式サイト）のリポジトリです。データセットの説明は [docs/index.md](docs/index.md) にあります。

## 人が直すとき

確認できない団体・機関は、[docs/index.md](docs/index.md) の「使い方」の SQL で引いて見ます。サイトを確認したら、`record.py` で記録します。記録は `official_site_history` に、記録した人と理由とともに 1 行追記されます。対象は、地方公共団体なら全国地方公共団体コード、国の機関なら法人番号で指定します。

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
