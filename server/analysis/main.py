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
from graph_builder import GraphBuilder, EpisodeTimeline
from storage import AnalysisStorage
from speaker_identifier import SpeakerIdentifier


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
    force: bool = False,
    episode: dict = None
) -> dict:
    """分析单个剧集"""
    print(f"\n{'='*60}")
    print(f"开始分析: {video_url}")
    print(f"{'='*60}")

    # 断点续传：检查状态
    if not force:
        current_status = storage.get_status(video_url)
        if current_status == "completed":
            cached = storage.get_episode_analysis(video_url)
            if cached:
                print(f"✓ 已完成，跳过（使用 --force 强制重新分析）")
                return cached

    storage.mark_status(video_url, "in_progress")

    preprocessor = VideoPreprocessor(Config.FRAME_DIR)
    frames = preprocessor.extract_key_frames_smart(
        video_path,
        str(Path(Config.FRAME_DIR) / video_url.replace("/", "_")),
        num_frames=Config.FRAMES_PER_EPISODE
    )

    if not frames:
        raise RuntimeError("抽帧失败，未获取到任何帧")

    print(f"\n开始调用多模态模型分析 {len(frames)} 帧...")
    # 增量保存断点
    checkpoint = str(
            Path(Config.OUTPUT_DIR)
            / f"frames_checkpoint_{video_url.replace('/', '_').replace(chr(92), '_')}.json"
        )
    frame_analyses = analyzer.analyze_frames_batch(
        frames, delay=0.5, checkpoint_path=checkpoint
    )

    print(f"\n开始LLM结构化提取...")
    structured = extractor.extract_summary(
        frame_analyses,
        episode_title=Path(video_path).parent.name
    )

    video_duration = preprocessor._get_duration(video_path)
    print(f"视频时长: {video_duration:.1f} 秒")

    # ---- 时间轴融合 + 高光检测 ----
    print(f"\n开始时间轴融合 + 高光检测...")
    # 准备音频片段
    audio_segments = []
    audio_result = None
    audio_analyzer = None
    if Config.AUDIO_ENABLED:
        try:
            from audio_analyzer import AudioAnalyzer
            audio_analyzer = AudioAnalyzer(device=Config.AUDIO_DEVICE)
            audio_result = audio_analyzer.analyze_full(video_path)
            audio_segments = audio_result.get("dialogue", [])
            print(f"  音频分析完成: {len(audio_segments)} 条对话")
        except ImportError as e:
            print(f"  ⚠ 音频分析跳过（缺少依赖）: {e}")
        except Exception as e:
            print(f"  ⚠ 音频分析失败: {e}")

    # 构建融合时间轴
    timeline = EpisodeTimeline(
        episode_title=Path(video_path).parent.name,
        video_url=video_url
    )
    timeline.build(
        audio_segments=audio_segments,
        frame_analyses=frame_analyses,
        frame_interval=Config.FRAME_INTERVAL_SECONDS,
        video_duration=video_duration
    )

    # 高光输出
    highlights = timeline.get_highlights_as_percentages(video_duration)
    structured["highlights_auto"] = highlights
    structured["timeline"] = timeline.to_dict()
    structured["highlight_intervals"] = timeline.highlights

    print(f"  时间轴: {len(timeline.segments)} 个片段")
    print(f"  高光区间: {len(timeline.highlights)} 个")
    print(f"  高光点(百分比): {highlights}")

    # 保存时间轴结果
    safe_name = video_url.replace("/", "_").replace("\\", "_")
    timeline_path = str(Path(Config.OUTPUT_DIR) / f"timeline_{safe_name}.json")
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"  时间轴已保存: {timeline_path}")

    structured["video_url"] = video_url
    structured["video_duration"] = video_duration
    structured["confidence_score"] = 0.8
    structured["frames_used"] = len(frames)
    structured["cost_estimate"] = len(frames) * 0.012
    structured["analyzed_at"] = datetime.now().isoformat()

    # ---- ASR驱动的说话人识别（可选，需AUDIO_ENABLED） ----
    speaker_map = {}
    if audio_analyzer is not None and audio_result is not None:
        try:
            print(f"\n开始说话人识别...")
            si = SpeakerIdentifier(analyzer, preprocessor, Config.FRAME_DIR)
            characters_context = structured.get("characters", [])
            si_result = si.identify_speakers_for_episode(
                video_path, video_url, audio_result,
                context_characters=characters_context
            )
            speaker_map = si_result.get("speaker_map", {})
            structured["speaker_map"] = speaker_map
            structured["speaker_identifications"] = si_result.get("identifications", [])

            # Save speaker identification results
            spk_output = str(Path(Config.OUTPUT_DIR) / "speaker_identities.json")
            si.save_to_file(si_result, spk_output)

            print(f"  说话人识别结果: {speaker_map}")
        except ImportError as e:
            print(f"  ⚠ 音频分析跳过（缺少依赖）: {e}")
        except Exception as e:
            print(f"  ⚠ 音频分析失败: {e}")
            import traceback
            traceback.print_exc()

    episode_graph = graph_builder.build_episode_graph(structured, video_url)
    # drama_id: 优先从 episode 数据获取，fallback 到 1
    drama_id = episode.get("drama_id", 1) if episode else 1
    global_graph = graph_builder.merge_global_graph(episode_graph, drama_id=drama_id)
    graph_builder.save_global_graph(global_graph)

    storage.update_episode_analysis(video_url, structured)

    storage.mark_status(video_url, "completed")

    # ---- 清理临时文件 ----
    episode_frame_dir = Path(Config.FRAME_DIR) / video_url.replace("/", "_")
    preprocessor.cleanup_frames(str(episode_frame_dir))
    if audio_result and "audio_path" in audio_result:
        preprocessor.cleanup_temp_audio(audio_result["audio_path"])

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
    parser.add_argument("--resume", action="store_true", help="断点续传，跳过已完成的剧集")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    args = parser.parse_args()

    if not Config.DOUBAO_API_KEY:
        print("错误: 请设置 DOUBAO_API_KEY 环境变量")
        print("  Windows: set DOUBAO_API_KEY=your_api_key")
        print("  Linux/Mac: export DOUBAO_API_KEY=your_api_key")
        sys.exit(1)

    analyzer = MultimodalAnalyzer(
        api_key=Config.DOUBAO_API_KEY,
        base_url=Config.DOUBAO_BASE_URL,
        model=Config.DOUBAO_VL_MODEL
    )
    extractor = StructuredExtractor(
        api_key=Config.DOUBAO_API_KEY,
        base_url=Config.DOUBAO_BASE_URL,
        model=Config.DOUBAO_LLM_MODEL
    )
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
        
        if args.resume:
            completed = storage.get_completed()
            episodes = [e for e in episodes if e.get("video_url", "") not in completed]
            print(f"断点续传: {len(episodes)} 个待分析剧集 (已跳过 {len(completed)} 个已完成)")

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
                        force=args.force,
                        episode=episode
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
            force=args.force,
            episode=None
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
            force=args.force,
            episode=None
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
                        force=args.force,
                        episode=episode
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
