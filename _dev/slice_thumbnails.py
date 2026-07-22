#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
切割 12 宮格燈光成品圖成縮圖。
掃描標籤帶位置，按照實際格線切割。
"""

from PIL import Image
import numpy as np
from pathlib import Path

# 檔名對照表
FILENAME_MAP = {
    (0, 0): 'futuristic.png',      # 未來感
    (0, 1): 'angel.png',            # 天使光
    (0, 2): 'simple_panel.png',     # 簡單光板
    (0, 3): 'studio.png',           # 一般棚燈
    (1, 0): 'influencer.png',       # 網紅
    (1, 1): 'blinds.png',           # 百葉窗
    (1, 2): 'sunset.png',           # 夕陽氛圍
    (1, 3): 'moody.png',            # 憂鬱
    (2, 0): 'horror.png',           # 靈異
    (2, 1): 'beauty_ring.png',      # 網美
    (2, 2): 'gradient.png',         # 漸層
    (2, 3): 'retro.png',            # 復古
}

def detect_label_bands(image_array):
    """
    掃描每一列下方像素的亮度，找出淺色標籤帶的 y 範圍。
    標籤帶通常比深色背景亮得多。

    Returns: List of (band_y_start, band_y_end) tuples，共 3 個
    """
    # 轉換成灰度來計算亮度
    if len(image_array.shape) == 3:
        gray = np.mean(image_array, axis=2)  # 取平均
    else:
        gray = image_array

    height = gray.shape[0]

    # 逐行掃描亮度，找出高亮區域
    row_brightness = np.mean(gray, axis=1)

    # 計算動態閾值：取平均 + 標準差的某個倍數
    mean_brightness = np.mean(row_brightness)
    std_brightness = np.std(row_brightness)
    threshold = mean_brightness + 1.5 * std_brightness

    # 找出連續的高亮行
    bright_mask = row_brightness > threshold

    bands = []
    in_band = False
    band_start = 0

    for y in range(height):
        if bright_mask[y] and not in_band:
            band_start = y
            in_band = True
        elif not bright_mask[y] and in_band:
            bands.append((band_start, y))
            in_band = False

    if in_band:
        bands.append((band_start, height))

    return bands

def slice_image(source_path, output_dir):
    """
    切割圖片並存檔。
    """
    # 讀進圖片
    img = Image.open(source_path)
    img_array = np.array(img)

    width, height = img.size
    print(f"圖片尺寸: {width} x {height}")

    # 掃描標籤帶位置
    bands = detect_label_bands(img_array)
    print(f"偵測到 {len(bands)} 條標籤帶:")
    for i, (y_start, y_end) in enumerate(bands):
        print(f"  第 {i+1} 列標籤帶: y {y_start} ~ {y_end}")

    if len(bands) != 3:
        print(f"警告: 預期 3 條標籤帶，但只找到 {len(bands)} 條")
        if len(bands) < 3:
            print("無法自動切割，請檢查圖片或手動調整")
            return False

    # 基於標籤帶位置推算每一列圖片區的上下界
    row_bounds = []

    # 第 1 列: 從 0 到第 1 條標籤帶的開始
    row_bounds.append((0, bands[0][0]))

    # 第 2 列: 從第 1 條標籤帶的結尾到第 2 條標籤帶的開始
    row_bounds.append((bands[0][1], bands[1][0]))

    # 第 3 列: 從第 2 條標籤帶的結尾到第 3 條標籤帶的開始
    row_bounds.append((bands[1][1], bands[2][0]))

    print("\n實際格線位置:")
    for i, (y_start, y_end) in enumerate(row_bounds):
        print(f"  第 {i+1} 列圖片區: y {y_start} ~ {y_end} (高度 {y_end - y_start})")

    # 欄寬等分 4 份
    col_width = width // 4
    col_bounds = [(i * col_width, (i + 1) * col_width) for i in range(4)]

    print("\n欄寬:")
    for i, (x_start, x_end) in enumerate(col_bounds):
        print(f"  第 {i+1} 欄: x {x_start} ~ {x_end}")

    # 切割每一格
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    success_count = 0
    for row_idx, (y_start, y_end) in enumerate(row_bounds):
        for col_idx, (x_start, x_end) in enumerate(col_bounds):
            # 切割原始區域
            crop_box = (x_start, y_start, x_end, y_end)
            cropped = img.crop(crop_box)

            # 轉成正方形（置中裁切）
            w, h = cropped.size
            size = min(w, h)
            left = (w - size) // 2
            top = (h - size) // 2
            squared = cropped.crop((left, top, left + size, top + size))

            # 縮到 256x256
            thumbnail = squared.resize((256, 256), Image.Resampling.LANCZOS)

            # 存檔
            filename = FILENAME_MAP.get((row_idx, col_idx))
            if filename:
                output_file = output_path / filename
                thumbnail.save(output_file, 'PNG')
                print(f"OK {filename}")
                success_count += 1
            else:
                print(f"ERR 未知的位置 ({row_idx}, {col_idx})")

    print(f"\n完成: {success_count} 個檔案")
    return success_count == 12

if __name__ == '__main__':
    source = Path('D:/Dropbox/Zack/03_品牌經營/名單磁鐵/封存/燈光模板/12 Lighting Scene for Character/目錄.png')
    output = 'D:/Dropbox/Zack/03_品牌經營/名單磁鐵/免費插件/Character Lighting 12/thumbnails'

    if not source.exists():
        print(f"錯誤: 找不到來源檔案 {source}")
        exit(1)

    slice_image(source, output)
