#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

# 実際のHTMLを取得して解析
response = requests.get('https://www.kyoto-su.ac.jp/bus/kamigamo/')
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, 'html.parser')

print("=== テーブル構造の確認 ===")
tables = soup.find_all('table')
print(f"テーブル数: {len(tables)}")

for i, table in enumerate(tables):
    print(f"\n--- テーブル {i+1} ---")
    rows = table.find_all('tr')
    print(f"行数: {len(rows)}")
    
    if rows:
        # ヘッダー行を確認
        header = rows[0]
        cells = header.find_all(['th', 'td'])
        print(f"ヘッダーセル数: {len(cells)}")
        for j, cell in enumerate(cells):
            print(f"  セル{j}: '{cell.get_text().strip()}'")
        
        # 最初の数行のデータを確認
        print("\n最初の5行のデータ:")
        for k, row in enumerate(rows[1:6]):
            cells = row.find_all(['th', 'td'])
            if cells:
                row_data = [cell.get_text().strip() for cell in cells]
                print(f"  行{k+1}: {row_data}")

print("\n=== テキスト全体から時刻表パターンを探す ===")
text = soup.get_text()
lines = text.split('\n')

# 時刻表らしい行を探す
for i, line in enumerate(lines):
    line = line.strip()
    if re.match(r'^\d{1,2}\s+', line) and ('・' in line or '分間隔' in line):
        print(f"行{i}: {line}")
        if i < len(lines) - 1:
            print(f"次行: {lines[i+1].strip()}")
        print()