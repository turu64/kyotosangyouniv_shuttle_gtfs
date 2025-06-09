#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
京都産業大学シャトルバス時刻表HTMLからGTFSデータを生成するスクリプト

使用方法:
    python timetable_to_gtfs.py --input schedule.html --route-id 50000
"""

import csv
import argparse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Tuple
import os
import requests


class TimetableParser:
    """HTML時刻表を解析してGTFSデータを生成するクラス"""
    
    def __init__(self, route_id: str, route_config: Dict):
        self.route_id = route_id
        self.config = route_config
        self.trips = []
        self.stop_times = []
        
    def parse_html(self, html_content: str) -> None:
        """HTML時刻表を解析"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # テーブルを探す
        table = soup.find('table')
        if not table:
            raise ValueError("時刻表のテーブルが見つかりません")
            
        rows = table.find_all('tr')
        if len(rows) < 3:
            raise ValueError("テーブルの行数が不足しています")
        
        # ヘッダー構造を解析（1行目：曜日、2行目：方向）
        service_patterns = self._parse_complex_header(rows[0], rows[1])
        
        # 時刻データを解析（3行目以降）
        for row in rows[2:]:
            self._parse_time_row(row, service_patterns)
    
    def _parse_complex_header(self, day_row, direction_row) -> List[Dict]:
        """複合ヘッダー（曜日行と方向行）を解析"""
        day_cells = day_row.find_all(['th', 'td'])
        direction_cells = direction_row.find_all(['th', 'td'])
        
        patterns = []
        
        # 曜日セルの情報を取得
        day_info = []
        for cell in day_cells[1:]:  # 最初のセルは"時間"
            text = cell.get_text().strip()
            if "月～金曜日（水曜日除く）" in text:
                day_info.append('weekday')
            elif "水曜日" in text:
                day_info.append('wednesday')
            elif "土曜日" in text:
                day_info.append('saturday')
            else:
                day_info.append('unknown')
        
        # 方向セルと曜日セルを組み合わせてパターンを作成
        col_index = 0
        for i, cell in enumerate(direction_cells[1:]):  # 最初のセルは"大学発"
            text = cell.get_text().strip()
            
            # 曜日情報を決定
            day_type = 'unknown'
            if i == 0 or i == 1:  # 月～金（水除く）
                day_type = 'weekday'
                service_id = 'O_0001_1'
            elif i == 2 or i == 3:  # 水曜日
                day_type = 'wednesday'
                service_id = 'O_0001_5'
            elif i == 4 or i == 5:  # 土曜日
                day_type = 'saturday'
                service_id = 'O_0001_2'
            else:
                continue
            
            # 方向を決定
            direction = 0 if "大学発" in text else 1
            
            patterns.append({
                'index': col_index,
                'service_id': service_id,
                'direction': direction,
                'day_type': day_type
            })
            col_index += 1
                
        return patterns
    
    def _parse_text_format(self, text: str) -> None:
        """テキスト形式の時刻表を解析"""
        lines = text.split('\n')
        
        # 固定の列構成パターンを定義
        service_patterns = [
            {'index': 0, 'service_id': 'O_0001_1', 'direction': 0},  # 月～金（水除く）大学発
            {'index': 1, 'service_id': 'O_0001_1', 'direction': 1},  # 月～金（水除く）神社発
            {'index': 2, 'service_id': 'O_0001_5', 'direction': 0},  # 水曜日大学発
            {'index': 3, 'service_id': 'O_0001_5', 'direction': 1},  # 水曜日神社発
            {'index': 4, 'service_id': 'O_0001_2', 'direction': 0},  # 土曜日大学発
            {'index': 5, 'service_id': 'O_0001_2', 'direction': 1},  # 土曜日神社発
        ]
        
        # 時刻データを探す
        for line in lines:
            line = line.strip()
            # 時間で始まる行を探す
            if re.match(r'^\d{1,2}\s+', line):
                parts = re.split(r'\s{2,}', line)  # 2つ以上の空白で分割
                if len(parts) >= 2:
                    try:
                        hour = int(parts[0])
                        # 各列の時刻データを処理
                        for i, time_data in enumerate(parts[1:]):
                            if i < len(service_patterns) and time_data.strip():
                                pattern = service_patterns[i]
                                self._parse_times(time_data.strip(), hour, pattern)
                    except ValueError:
                        continue
    
    def _parse_time_row(self, row, service_patterns: List[Dict]) -> None:
        """各行の時刻データを解析"""
        cells = row.find_all(['th', 'td'])
        if len(cells) < 2:
            return
            
        # 時間を取得
        hour_text = cells[0].get_text().strip()
        try:
            hour = int(hour_text)
        except ValueError:
            return
            
        # 各セルの時刻を解析
        for i, cell in enumerate(cells[1:]):
            times_text = cell.get_text().strip()
            if not times_text:
                continue
                
            # 対応するservice_patternを探す
            pattern = None
            for p in service_patterns:
                if p['index'] == i:
                    pattern = p
                    break
                    
            if not pattern:
                continue
                
            # 時刻を解析
            self._parse_times(times_text, hour, pattern)
    
    def _parse_times(self, times_text: str, hour: int, pattern: Dict) -> None:
        """時刻テキストを解析してtrip/stop_timeを生成"""
        # "以降5～10分間隔"のパターン
        interval_match = re.search(r'以降(\d+)～(\d+)分間隔', times_text)
        if interval_match:
            # 間隔運行として処理
            min_interval = int(interval_match.group(1))
            max_interval = int(interval_match.group(2))
            
            # その前の固定時刻を取得
            fixed_times = re.findall(r'(\d{2})(?:・|$)', times_text.split('以降')[0])
            
            # 固定時刻を処理
            for minute_str in fixed_times:
                self._create_trip(hour, int(minute_str), pattern)
                
            # 間隔運行の情報を記録（frequencies.txtで使用）
            if fixed_times:
                last_minute = int(fixed_times[-1])
                self._create_frequency_trip(hour, last_minute, min_interval, pattern)
        else:
            # 固定時刻のみ
            minutes = re.findall(r'(\d{2})(?:・|$)', times_text)
            for minute_str in minutes:
                self._create_trip(hour, int(minute_str), pattern)
    
    def _create_trip(self, hour: int, minute: int, pattern: Dict) -> None:
        """tripとstop_timeを生成"""
        # trip_idを生成
        trip_id = f"{self.route_id}_{pattern['service_id']}_{hour:02d}{minute:02d}_{pattern['direction']}"
        
        # 出発/到着時刻を計算
        departure_time = f"{hour:02d}:{minute:02d}:00"
        
        # 所要時間（設定から取得、デフォルトは15分）
        # 方向別の所要時間がある場合はそれを使用
        if isinstance(self.config.get('travel_time_minutes'), dict):
            travel_time = self.config['travel_time_minutes'][pattern['direction']]
        else:
            travel_time = self.config.get('travel_time_minutes', 15)
        arrival_hour = hour
        arrival_minute = minute + travel_time
        
        # 時刻の調整
        if arrival_minute >= 60:
            arrival_hour += arrival_minute // 60
            arrival_minute = arrival_minute % 60
            
        arrival_time = f"{arrival_hour:02d}:{arrival_minute:02d}:00"
        
        # trip情報
        trip = {
            'route_id': self.route_id,
            'service_id': pattern['service_id'],
            'trip_id': trip_id,
            'trip_headsign': self.config['headsigns'][pattern['direction']],
            'direction_id': pattern['direction'],
            'block_id': '',
            'shape_id': '',
            'wheelchair_accessible': '1',
            'bikes_allowed': '2'
        }
        self.trips.append(trip)
        
        # stop_times情報
        stops = self.config['stops'][pattern['direction']]
        for i, (stop_id, is_departure) in enumerate(stops):
            if i == 0:
                # 始発停留所
                stop_time = {
                    'trip_id': trip_id,
                    'arrival_time': departure_time,
                    'departure_time': departure_time,
                    'stop_id': stop_id,
                    'stop_sequence': i + 1,
                    'stop_headsign': '',
                    'pickup_type': '0',
                    'drop_off_type': '1',  # 降車不可
                    'shape_dist_traveled': '',
                    'timepoint': '1'
                }
            else:
                # 終着停留所
                stop_time = {
                    'trip_id': trip_id,
                    'arrival_time': arrival_time,
                    'departure_time': arrival_time,
                    'stop_id': stop_id,
                    'stop_sequence': i + 1,
                    'stop_headsign': '',
                    'pickup_type': '1',  # 乗車不可
                    'drop_off_type': '0',
                    'shape_dist_traveled': '',
                    'timepoint': '1'
                }
            self.stop_times.append(stop_time)
    
    def _create_frequency_trip(self, hour: int, start_minute: int, interval: int, pattern: Dict) -> None:
        """間隔運行の情報を記録（将来的にfrequencies.txtで使用）"""
        # TODO: frequencies.txtの生成に対応
        pass
    
    def save_gtfs(self, output_dir: str = '.') -> None:
        """GTFSファイルを保存"""
        # trips.txt
        trips_path = os.path.join(output_dir, 'trips.txt')
        with open(trips_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'route_id', 'service_id', 'trip_id', 'trip_headsign',
                'direction_id', 'block_id', 'shape_id',
                'wheelchair_accessible', 'bikes_allowed'
            ])
            writer.writeheader()
            writer.writerows(self.trips)
        
        # stop_times.txt
        stop_times_path = os.path.join(output_dir, 'stop_times.txt')
        with open(stop_times_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'trip_id', 'arrival_time', 'departure_time', 'stop_id',
                'stop_sequence', 'stop_headsign', 'pickup_type',
                'drop_off_type', 'shape_dist_traveled', 'timepoint'
            ])
            writer.writeheader()
            writer.writerows(self.stop_times)
        
        print(f"Generated {len(self.trips)} trips and {len(self.stop_times)} stop times")
        print(f"Files saved: {trips_path}, {stop_times_path}")


# ルート設定
ROUTE_CONFIGS = {
    '50000': {  # 上賀茂シャトル
        'travel_time_minutes': 6,
        'headsigns': {
            0: '上賀茂神社前',
            1: '京都産業大学前'
        },
        'stops': {
            0: [('7475_A', True), ('129A00', False)],  # 大学→神社
            1: [('129A00', True), ('7475_A', False)]   # 神社→大学
        }
    },
    '50001': {  # 上賀茂シャトル（迂回）
        'travel_time_minutes': {
            0: 5,  # 下り（大学→西賀茂車庫）
            1: 8   # 上り（西賀茂車庫→大学）
        },
        'headsigns': {
            0: '西賀茂車庫',
            1: '京都産業大学前'
        },
        'stops': {
            0: [('7475_A', True), ('034A20', False)],  # 大学→西賀茂車庫
            1: [('034A20', True), ('7475_A', False)]   # 西賀茂車庫→大学
        }
    },
    '50002': {  # 二軒茶屋シャトル
        'travel_time_minutes': 6,
        'headsigns': {
            0: '二軒茶屋駅前',
            1: '京都産業大学前'
        },
        'stops': {
            0: [('7475_A', True), ('6196_A', False)],  # 大学→二軒茶屋
            1: [('6196_A', True), ('7475_A', False)]   # 二軒茶屋→大学
        }
    },
    '50003': {  # 体育館シャトル
        'travel_time_minutes': 10,
        'headsigns': {
            0: '総合グラウンド',
            1: '京都産業大学前'
        },
        'stops': {
            0: [('7475_A', True), ('566A00', False)],  # 大学→総合グラウンド
            1: [('566A00', True), ('7475_A', False)]   # 総合グラウンド→大学
        }
    }
}


def main():
    parser = argparse.ArgumentParser(description='HTML時刻表からGTFSデータを生成')
    parser.add_argument('--input', '-i', help='入力HTMLファイルまたはURL')
    parser.add_argument('--route-id', '-r', required=True, help='route_id (例: 50000)')
    parser.add_argument('--output-dir', '-o', default='.', help='出力ディレクトリ')
    parser.add_argument('--url', '-u', help='時刻表のURL（--inputの代わりに使用）')
    
    args = parser.parse_args()
    
    # 入力ソースの確認
    if not args.input and not args.url:
        print("Error: --input または --url のいずれかを指定してください")
        return
    
    # ルート設定を取得
    if args.route_id not in ROUTE_CONFIGS:
        print(f"Error: Unknown route_id: {args.route_id}")
        print(f"Available route_ids: {', '.join(ROUTE_CONFIGS.keys())}")
        return
    
    config = ROUTE_CONFIGS[args.route_id]
    
    # HTMLコンテンツを取得
    if args.url:
        print(f"Fetching from URL: {args.url}")
        response = requests.get(args.url)
        response.encoding = 'utf-8'
        html_content = response.text
    else:
        # HTMLファイルを読み込み
        with open(args.input, 'r', encoding='utf-8') as f:
            html_content = f.read()
    
    # 解析と変換
    parser = TimetableParser(args.route_id, config)
    parser.parse_html(html_content)
    parser.save_gtfs(args.output_dir)


if __name__ == '__main__':
    main()