#!/usr/bin/env python3
"""
短剧AI分析主脚本
用法:
    python main.py                          # 分析所有剧集
    python main.py --episode 1           # 分析指定剧集
    python main.py --drama "天下第一纨绔"  # 分析指定剧的所有集
    python main.py --force                # 强制重新分析（忽略缓存）
    python main.py --stats                # 显示统计信息
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from video_preprocessor import VideoPreprocessor
from multimodal_analyzer import MultimodalAnalyzer
from structured_extractor import StructuredExtractor
from graph_builder import GraphBuilder
from storage import AnalysisStorage


def load_episodes():
    """从drama.json加载剧集列表"""
    with open(Config.LOWDB_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("episodes", [])


def analyze_episode(
    video_url: str,
    video_path: str,
    analyzer: MultimodalAnalyzer,
    extractor: StructuredExtractor,
    graph_builder: GraphBuilder,
    storage: AnalysisStorage,
    force: bool = False
) -> dict:
    """分析单个剧集"""
    print(f"\n{'='*60}")
    print(f"开始分析: {video_url}")
    print(f"{'='*60}")

    if not force:
        cached = storage.get_episode_analysis(video_url)
        if cached:
            print(f"✓ 已存在分析结果，跳过（使用 --force 强制重新分析）")
            return cached

    preprocessor = VideoPreprocessor(Config.FRAME_DIR)
    frames = preprocessor.extract_key_frames(
        video_path,
        str(Path(Config.FRAME_DIR) / video_url.replace("/", "_")),
        num_frames=Config.FRAMES_PER_EPISODE
    )

    if not frames:
        raise RuntimeError("抽帧失败，未获取到任何帧")

    print(f"\n开始调用Qwen-VL分析 {len(frames)} 帧...")
    frame_analyses = analyzer.analyze_frames_batch(frames, delay=0.5)

    print(f"\n开始LLM结构化提取...")
    structured = extractor.extract_summary(
        frame_analyses,
        episode_title=Path(video_path).parent.name
    )

    video_duration = preprocessor._get_duration(video_path)
    print(f"视频时长: {video_duration:.1f} 秒")

    highlights = extractor.map_to_highlights(
        structured.get("key_scenes", []),
        video_duration
    )
    structured["highlights_auto"] = highlights

    structured["video_url"] = video_url
    structured["video_duration"] = video_duration
    structured["confidence_score"] = 0.8
    structured["frames_used"] = len(frames)
    structured["cost_estimate"] = len(frames) * 0.012
    structured["analyzed_at"] = datetime.now().isoformat()

    episode_graph = graph_builder.build_episode_graph(structured, video_url)
    global_graph = graph_builder.merge_global_graph(episode_graph, drama_id=1)
    graph_builder.save_global_graph(global_graph)

    storage.update_episode_analysis(video_url, structured)

    print(f"\n✓ 分析完成!")
    print(f"  - 识别人物: {len(structured.get('characters', []))}")
    print(f"  - 关系数量: {len(structured.get('relationships', []))}")
    print(f"  - 关键场景: {len(structured.get('key_scenes', []))}")
    print(f"  - 自动高光点: {highlights}")
    print(f"  - 估算费用: ¥{structured['cost_estimate']:.2f}")

    return structured


def main():
    parser = argparse.ArgumentParser(description="短剧AI分析工具")
    parser.add_argument("--episode", type=int, help="分析指定剧集ID")
    parser.add_argument("--video-url", type=str, help="分析指定video_url的剧集")
    parser.add_argument("--drama", type=str, help="分析指定剧名的所有集")
    parser.add_argument("--force", action="store_true", help="强制重新分析")
    parser.add_argument("--all", action="store_true", help="分析所有剧集")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    args = parser.parse_args()

    if not Config.QWEN_API_KEY:
        print("错误: 请设置 QWEN_API_KEY 环境变量")
        print("  Windows: set QWEN_API_KEY=your_api_key")
        print("  Linux/Mac: export QWEN_API_KEY=your_api_key")
        sys.exit(1)

    analyzer = MultimodalAnalyzer(Config.QWEN_API_KEY, Config.QWEN_MODEL)
    extractor = StructuredExtractor(Config.QWEN_API_KEY)
    graph_builder = GraphBuilder(Config.GRAPH_FILE)
    storage = AnalysisStorage(Config.ANALYSIS_RESULTS_PATH)

    if args.stats:
        stats = storage.get_statistics()
        print("\n=== 分析统计 ===")
        print(f"已分析剧集数: {stats['total_analyses']}")
        print(f"总人物数: {stats['total_characters']}")
        print(f"总关键场景数: {stats['total_key_scenes']}")
        return

    if args.all:
        episodes = load_episodes()

        for episode in episodes:
            video_url = episode.get("video_url", "")
            if not video_url:
                continue

            video_path = Path(Config.VIDEO_DIR) / video_url
            if video_path.exists():
                try:
                    analyze_episode(
                        video_url,
                        str(video_path),
                        analyzer, extractor, graph_builder, storage,
                        force=args.force
                    )
                except Exception as e:
                    print(f"✗ 分析失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠ 视频文件不存在: {video_path}")

    elif args.video_url:
        video_url = args.video_url
        video_path = Path(Config.VIDEO_DIR) / video_url

        if not video_path.exists():
            print(f"✗ 视频文件不存在: {video_path}")
            return

        analyze_episode(
            video_url,
            str(video_path),
            analyzer, extractor, graph_builder, storage,
            force=args.force
        )

    elif args.episode:
        episodes = load_episodes()
        episode = next((e for e in episodes if e["id"] == args.episode), None)

        if not episode:
            print(f"✗ 剧集 #{args.episode} 不存在")
            return

        video_url = episode.get("video_url", "")
        video_path = Path(Config.VIDEO_DIR) / video_url

        if not video_path.exists():
            print(f"✗ 视频文件不存在: {video_path}")
            return

        analyze_episode(
            video_url,
            str(video_path),
            analyzer, extractor, graph_builder, storage,
            force=args.force
        )

    elif args.drama:
        print(f"分析剧名包含 '{args.drama}' 的所有集...")
        episodes = load_episodes()
        matched = [
            ep for ep in episodes
            if args.drama in ep.get("title", "")
        ]

        for episode in matched:
            video_url = episode.get("video_url", "")
            video_path = Path(Config.VIDEO_DIR) / video_url

            if video_path.exists():
                try:
                    analyze_episode(
                        video_url,
                        str(video_path),
                        analyzer, extractor, graph_builder, storage,
                        force=args.force
                    )
                except Exception as e:
                    print(f"✗ 分析失败: {e}")
            else:
                print(f"⚠ 视频文件不存在: {video_path}")

    else:
        print("请指定要分析的剧集:")
        print("  --all              分析所有剧集")
        print("  --episode <id>     分析指定剧集")
        print("  --video-url <url>  分析指定video_url的剧集")
        print("  --drama <name>     分析指定剧的所有集")
        print("  --stats            显示统计信息")
        print("\n示例:")
        print("  python main.py --video-url '天下第一纨绔/第1集.mp4'")
        print("  python main.py --all --force")


if __name__ == "__main__":
    main()
