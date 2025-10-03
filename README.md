# kyotosangyouniv_shuttle_gtfs

京都産業大学が京都バスに運行を委託しているシャトルバスの非公式GTFS-JPデータです。

学校法人京都産業大学や京都バス株式会社とは全く無関係です。直接のお問い合わせはご遠慮ください。

このデータに関するお問い合わせはこのGitHubリポジトリのIssueまたはturu64までお願いします。

データの形式は基本的に国土交通省の[静的バス情報フォーマット（GTFS-JP）仕様書（第３版）](https://www.mlit.go.jp/sogoseisaku/transport/sosei_transport_tk_000112.html)に準じますが、[京都バスが公開しているGTFS-JPオープンデータ](https://ckan.odpt.org/organization/kyoto_bus)や[京都市営バスが公開しているGTFS-JPオープンデータ](https://ckan.odpt.org/dataset/kyoto_municipal_transportation_kyoto_city_bus_gtfs)での記述や表現方法を優先的に使用します。

このGTFS-JPデータでは以下の路線情報を収録しています。

* 上賀茂シャトル
* 上賀茂シャトル（葵祭迂回・西賀茂車庫行き）
* 二軒茶屋シャトル
* 体育館シャトル（本学↔総合グラウンド）

※本山寮シャトルは寮生以外の利用を防ぐ観点から、収録していません。

### 概要

このリポジトリは、京都産業大学のシャトルバス時刻表（HTML）からGTFS-JPの一部ファイルを生成し、他の静的ファイルとともに配布するためのプロジェクトです。主に以下のPythonスクリプトを含みます。

- `timetable_to_gtfs.py`: 大学サイト上の時刻表HTML（またはローカルHTML）を解析し、`trips.txt` と `stop_times.txt` を生成します。
- `debug_parser.py`: 元HTMLのテーブル構造を調査するためのデバッグ用スクリプトです。

既存の `agency.txt` などのGTFS-JPファイルは手元で管理され、本スクリプトは現在 `trips.txt` と `stop_times.txt` のみを上書き生成します。

### 前提条件

- Python 3.8以上を推奨
- パッケージ: `beautifulsoup4`, `requests`

インストール例（Windows PowerShell）:

```powershell
python -m pip install --upgrade pip
python -m pip install beautifulsoup4 requests
```

### 使い方（`timetable_to_gtfs.py`）

大学サイトの時刻表URLから直接生成するか、ローカルに保存したHTMLから生成できます。

- **URLから生成**

```powershell
python timetable_to_gtfs.py --url https://www.kyoto-su.ac.jp/bus/kamigamo/ --route-id 50000 --output-dir .
```
バージョン管理をして作成する例（--output-dirのあとのディレクトリの名前を変更しておく）：
```powershell
python timetable_to_gtfs.py --url https://www.kyoto-su.ac.jp/bus/kamigamo/ --route-id 50000 --output-dir ./20250929
```

- **ローカルHTMLから生成**

```powershell
python timetable_to_gtfs.py --input schedule.html --route-id 50000 --output-dir .
```

主な引数:

- `--route-id` / `-r`（必須）: 生成対象の路線ID（下記の一覧参照）
- `--url` / `-u`: 時刻表のURL。`--input`の代替
- `--input` / `-i`: ローカルHTMLファイルパス。`--url`の代替
- `--output-dir` / `-o`: 出力先ディレクトリ（既定: カレントディレクトリ）

出力:

- `trips.txt`（スクリプトが生成）
- `stop_times.txt`（スクリプトが生成）
- `gtfs-basefiles` 内のベースファイル（`agency.txt`、`routes.txt`、`stops.txt`、`calendar.txt`、`calendar_dates.txt`、`fare_*`、`feed_info.txt`、`translations.txt`、`office_jp.txt`、`pattern_jp.txt`、`frequencies.txt` など）が出力先へ自動コピーされます（`trips.txt`/`stop_times.txt` は除外）。

既存の同名ファイルは上書きされます。必要に応じて事前にバックアップしてください。

補足:

- ベースファイルはリポジトリ直下の `gtfs-basefiles` からコピーします。カスタマイズしたい場合は該当ディレクトリ内のテキストを編集してください。
- `--output-dir` を日付ディレクトリ（例: `./20250929`）にすることで版管理がしやすくなります。

### ルートID一覧（`--route-id`）

- `50000`: 上賀茂シャトル（大学↔上賀茂神社）
- `50001`: 上賀茂シャトル（葵祭迂回・大学↔西賀茂車庫）
- `50002`: 二軒茶屋シャトル（大学↔二軒茶屋駅）
- `50003`: 体育館シャトル（本学↔総合グラウンド）

停留所構成、方向別の行先名、所要時間などはスクリプト内の `ROUTE_CONFIGS` で定義されています（必要に応じて編集してください）。

### デバッグ（`debug_parser.py`）

元ページのテーブル構造や抽出されるテキストを確認したい場合:

```powershell
python debug_parser.py
```

ページのテーブル数、各テーブルの行数、ヘッダー内容、先頭数行のデータ例、時刻表らしい行の抽出結果を標準出力に表示します。

### 既知の制限・注意

- 時刻表内の「以降X～Y分間隔」といった間隔運行は、`trips.txt`/`stop_times.txt` では固定時刻部分のみを出力します。`frequencies.txt` の自動生成は未対応です。
- HTMLの構造変更や文言変更により、解析が失敗する場合があります。解析がうまくいかない場合は `debug_parser.py` で元HTMLを確認し、`timetable_to_gtfs.py` のヘッダー解析ロジック（`_parse_complex_header` など）を調整してください。
- 出力は現在の仕様上、学内向けシャトルに特化した設定です。他路線に流用する場合は `ROUTE_CONFIGS` を適切に拡張してください。

### ライセンス

本リポジトリのライセンスは `LICENSE` を参照してください。