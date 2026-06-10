#!/usr/bin/env python3
"""
视频目录监控进程 — 持久化运行，每分钟扫描 D:\video_data\videos
检测新增剧集 → 自动触发分析
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from collections import defaultdict

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════
WATCH_DIR = r"D:\video_data\videos"
SCAN_INTERVAL = 60          # 扫描间隔（秒）
ANALYSIS_SCRIPT = Path(__file__).parent / "run_analysis.py"
STATE_FILE = Path(__file__).parent / ".watcher_state.json"

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m3u8", ".avi", ".flv"}


def scan_videos() -> dict:
    """扫描目录，返回 {drama_name: [filename, ...]}"""
    dramas = defaultdict(list)
    root = Path(WATCH_DIR)
    if not root.exists():
        return {}
    for subdir in sorted(root.iterdir()):
        if not subdir.is_dir():
            continue
        videos = sorted(
            f.name for f in subdir.iterdir()
            if f.suffix.lower() in VIDEO_EXTS
        )
        if videos:
            dramas[subdir.name] = videos
    return dict(dramas)


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def detect_changes(old: dict, new: dict) -> dict:
    """对比新旧扫描结果，返回 {drama_name: [new_videos]}"""
    changes = {}
    for drama, videos in new.items():
        old_videos = set(old.get(drama, []))
        new_videos = [v for v in videos if v not in old_videos]
        if new_videos:
            changes[drama] = new_videos
    # 全新的剧（old中没有）
    for drama in new:
        if drama not in old:
            changes[drama] = new[drama]
    return changes


def trigger_analysis(drama: str, new_count: int):
    """触发分析：≤3集用 single 模式逐个跑，>3集用 drama 模式"""
    script = str(ANALYSIS_SCRIPT)
    python = sys.executable

    if new_count <= 3:
        print(f"  → 少量新增 ({new_count}集)，逐个 single 模式分析")
        # Scan to get video_urls
        current = scan_videos()
        videos = current.get(drama, [])
        for v in videos:
            video_url = f"{drama}/{v}"
            cmd = [
                python, script,
                "--mode", "single",
                "--video-url", video_url,
                "--resume"
            ]
            print(f"    $ {' '.join(cmd)}")
            subprocess.run(cmd, cwd=str(ANALYSIS_SCRIPT.parent))
    else:
        print(f"  → 大量新增 ({new_count}集)，drama 模式全量分析")
        cmd = [
            python, script,
            "--mode", "drama",
            "--drama", drama,
            "--resume"
        ]
        print(f"    $ {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(ANALYSIS_SCRIPT.parent))


def main():
    print("=" * 60)
    print("  短剧视频目录监控进程")
    print(f"  监控目录: {WATCH_DIR}")
    print(f"  扫描间隔: {SCAN_INTERVAL}s")
    print("=" * 60)

    # 首次扫描建立基线
    print("\n[初始化] 建立基线...")
    current = scan_videos()
    save_state(current)
    total = sum(len(v) for v in current.values())
    print(f"  发现 {len(current)} 部剧, {total} 个视频文件")
    for drama, videos in sorted(current.items()):
        print(f"    {drama}: {len(videos)} 集")

    print(f"\n[监控] 每 {SCAN_INTERVAL}s 扫描一次...")
    print("  Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(SCAN_INTERVAL)
            old = load_state()
            new = scan_videos()
            changes = detect_changes(old, new)

            if changes:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] 检测到变更:")
                for drama, vids in changes.items():
                    print(f"  {drama}: +{len(vids)} 集 {vids[:5]}{'...' if len(vids)>5 else ''}")
                    trigger_analysis(drama, len(vids))

                save_state(new)
            else:
                # 静默心跳
                ts = time.strftime("%H:%M:%S")
                print(f"  [{ts}] 无变更", end="\r")

    except KeyboardInterrupt:
        print("\n\n[停止] 监控进程已退出")


if __name__ == "__main__":
    main()
