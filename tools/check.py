"""data/official_site.csv の URL をすべて開いて確認し、一覧と履歴を書き換える。

- タイトルに団体名を含めば verified_at を今日にする
- そのうえでリダイレクトの先が違えば url を先の URL に替え、元の URL を data/official_site_history.csv に残す
- 開けない・タイトルが合わないときは url と verified_at を変えない (checked_at・http_status・page_title だけ書く)

uv run python tools/check.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sites import HISTORY, HISTORY_FIELDS, SITE_FIELDS, SITES, checked, fetch_all, read_csv, write_csv


def main() -> None:
    today = date.today().isoformat()
    rows = read_csv(SITES)
    results = [checked(r, p, today) for r, p in zip(rows, fetch_all([r["url"] for r in rows]))]
    write_csv(SITES, SITE_FIELDS, [r for r, _ in results])
    moved = [h for _, h in results if h]
    write_csv(HISTORY, HISTORY_FIELDS, read_csv(HISTORY) + moved)
    unverified = sum(r["verified_at"] != today for r, _ in results)
    print(f"{len(rows)} 件を確認: URL の変更 {len(moved)} 件、確認できなかった {unverified} 件")


if __name__ == "__main__":
    main()
