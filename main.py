"""公式サイトの一覧 (data/*.csv) をテーブルにする。

一覧の更新は tools/check.py が行い、ここでは取得しない。dbt だけを回す。
"""

import logging

from dbt.cli.main import dbtRunner

# dbt を読み込むとルートロガーが先に設定されるので、force で上書きする
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)


def main():
    dbt = dbtRunner()
    for args in (["deps"], ["build"], ["docs", "generate"]):
        if not dbt.invoke(args).success:
            raise SystemExit(f"dbt {args[0]} failed")


if __name__ == "__main__":
    main()
