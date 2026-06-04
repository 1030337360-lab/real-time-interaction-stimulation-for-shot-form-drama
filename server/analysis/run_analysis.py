#!/usr/bin/env python3
"""
一键分析脚本 - 修改下方参数后直接运行即可执行完整解析流程

用法:
    python run_analysis.py          # 按下方参数运行
"""

# ============================================================
# 参数配置区 - 只改这里
# ============================================================

# 分析模式: "all" / "drama" / "episode" / "single"
MODE = "single"

# MODE="all": 分析 drama.json 中所有剧集
ALL_RESUME = True     # 断点续传, 跳过已完成
ALL_FORCE = False     # 强制重跑全部

# MODE="drama": 分析指定剧名的所有集
DRAMA_NAME = "天下第一纨绔"

# MODE="episode": 分析指定ID的剧集
EPISODE_ID = 1

# MODE="single": 分析单个视频文件
SINGLE_VIDEO_URL = "天下第一纨绔/第63集.mp4"

# 功能开关
ENABLE_AUDIO = True          # 音频分析 (需 funasr)
ENABLE_SPEAKER_ID = True     # 说话人识别
ENABLE_CACHE = True          # 帧缓存 (省API费)
CLEANUP_TEMP = True          # 清理临时文件

# 参数调整
FRAMES_PER_EPISODE = 30      # 场景检测抽帧上限
HIGHLIGHT_TOP_K = 8          # 高光输出数量
SHOW_STATS = True            # 结束时显示统计

# ============================================================
# 执行逻辑 - 不需要修改
# ============================================================

import sys, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from video_preprocessor import VideoPreprocessor
from multimodal_analyzer import MultimodalAnalyzer
from structured_extractor import StructuredExtractor
from graph_builder import GraphBuilder, EpisodeTimeline
from storage import AnalysisStorage


def main():
    if not ENABLE_AUDIO:
        Config.AUDIO_ENABLED = False

    print("=" * 60)
    print("  短剧 AI 分析引擎")
    print("=" * 60)
    print(f"  模式: {MODE}")
    print(f"  音频: {'ON' if Config.AUDIO_ENABLED else 'OFF'}")
    print(f"  缓存: {'ON' if ENABLE_CACHE else 'OFF'}")
    print(f"  抽帧: {FRAMES_PER_EPISODE} 帧/集")
    print(f"  清理: {'ON' if CLEANUP_TEMP else 'OFF'}")
    print("=" * 60)

    if not Config.DOUBAO_API_KEY:
        print("\n[FATAL] 未设置 DOUBAO_API_KEY 环境变量")
        sys.exit(1)

    analyzer = MultimodalAnalyzer(
        api_key=Config.DOUBAO_API_KEY,
        base_url=Config.DOUBAO_BASE_URL,
        model=Config.DOUBAO_VL_MODEL
    )
    if not ENABLE_CACHE:
        analyzer.cache = None

    extractor = StructuredExtractor(
        api_key=Config.DOUBAO_API_KEY,
        base_url=Config.DOUBAO_BASE_URL,
        model=Config.DOUBAO_LLM_MODEL
    )
    graph_builder = GraphBuilder(Config.GRAPH_FILE)
    storage = AnalysisStorage(Config.ANALYSIS_RESULTS_PATH)
    preprocessor = VideoPreprocessor(Config.FRAME_DIR)

    t0 = datetime.now()

    if MODE == "all":
        _run_all(analyzer, extractor, graph_builder, storage, preprocessor)
    elif MODE == "drama":
        _run_drama(analyzer, extractor, graph_builder, storage, preprocessor)
    elif MODE == "episode":
        _run_episode(analyzer, extractor, graph_builder, storage, preprocessor)
    elif MODE == "single":
        _run_single(analyzer, extractor, graph_builder, storage, preprocessor)
    else:
        print(f"[FATAL] 未知模式: {MODE}")
        sys.exit(1)

    dt = (datetime.now() - t0).total_seconds()
    print(f"\n{'=' * 60}")
    print(f"  完成! {dt:.0f}s ({dt/60:.1f}min)")
    if ENABLE_CACHE and analyzer.cache:
        print(f"  缓存: {analyzer.cache.stats()['total_cached']} 条")
    if SHOW_STATS:
        s = storage.get_statistics()
        print(f"  剧集: {s['total_analyses']} | 人物: {s['total_characters']} | 场景: {s['total_key_scenes']}")
    print(f"{'=' * 60}")


def _load_episodes():
    with open(Config.LOWDB_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("episodes", [])


def _analyze_one(video_url, video_path, episode, analyzer, extractor,
                 graph_builder, storage, preprocessor, force=False):
    """分析单集完整流程"""
    print(f"\n{'='*60}")
    print(f"  {video_url}")
    print(f"{'='*60}")

    if not force:
        if storage.get_status(video_url) == "completed":
            c = storage.get_episode_analysis(video_url)
            if c:
                print("  [跳过] 已完成"); return c

    storage.mark_status(video_url, "in_progress")

    try:
        # 1. 抽帧
        print("  [1/5] 抽帧...")
        frames = preprocessor.extract_key_frames_smart(
            video_path,
            str(Path(Config.FRAME_DIR) / video_url.replace("/", "_").replace("\\", "_")),
            num_frames=FRAMES_PER_EPISODE
        )
        if not frames: raise RuntimeError("抽帧失败")

        # 2. VL
        print(f"  [2/5] VL分析 {len(frames)} 帧...")
        frame_analyses = analyzer.analyze_frames_batch(frames, delay=0.5)

        # 3. 音频
        audio_segments, audio_result = [], None
        if Config.AUDIO_ENABLED and ENABLE_AUDIO:
            try:
                from audio_analyzer import AudioAnalyzer
                print("  [3/5] 音频分析...")
                aa = AudioAnalyzer(device=Config.AUDIO_DEVICE)
                audio_result = aa.analyze_full(video_path)
                audio_segments = audio_result.get("dialogue", [])
            except ImportError:
                print("  [3/5] 音频跳过 (缺 funasr)")

        # 4. 时间轴
        print("  [4/5] 时间轴融合...")
        dur = preprocessor._get_duration(video_path)
        tl = EpisodeTimeline(Path(video_path).parent.name, video_url)
        tl.build(audio_segments, frame_analyses, Config.FRAME_INTERVAL_SECONDS, dur)

        # 5. 结构化
        print("  [5/5] LLM提取...")
        st = extractor.extract_summary(frame_analyses, Path(video_path).parent.name)

        # 组装
        st["highlights_auto"] = tl.get_highlights_as_percentages(dur)
        st["timeline"] = tl.to_dict()
        st["highlight_intervals"] = tl.highlights
        st["video_url"] = video_url
        st["video_duration"] = dur
        st["frames_used"] = len(frames)
        st["cost_estimate"] = round(len(frames) * 0.012, 2)
        st["analyzed_at"] = datetime.now().isoformat()

        # 说话人
        if ENABLE_SPEAKER_ID and audio_result:
            try:
                from speaker_identifier import SpeakerIdentifier
                print("  [附加] 说话人识别...")
                si = SpeakerIdentifier(analyzer, preprocessor, Config.FRAME_DIR)
                r = si.identify_speakers_for_episode(
                    video_path, video_url, audio_result,
                    context_characters=st.get("characters", [])
                )
                st["speaker_map"] = r.get("speaker_map", {})
            except Exception as e:
                print(f"  [警告] {e}")

        # 图谱
        did = episode.get("drama_id", 1) if episode else 1
        g = graph_builder.build_episode_graph(st, video_url)
        graph_builder.save_global_graph(graph_builder.merge_global_graph(g, did))

        storage.update_episode_analysis(video_url, st)
        storage.mark_status(video_url, "completed")

        # 时间轴文件
        tp = Path(Config.OUTPUT_DIR) / f"timeline_{video_url.replace('/', '_').replace(chr(92), '_')}.json"
        with open(tp, "w", encoding="utf-8") as f:
            json.dump(tl.to_dict(), f, ensure_ascii=False, indent=2)

        # 清理
        if CLEANUP_TEMP:
            fd = Path(Config.FRAME_DIR) / video_url.replace("/", "_").replace("\\", "_")
            preprocessor.cleanup_frames(str(fd))
            if audio_result and "audio_path" in audio_result:
                preprocessor.cleanup_temp_audio(audio_result["audio_path"])

        print(f"  [OK] 人物:{len(st.get('characters',[]))} 高光:{len(st['highlights_auto'])} "
              f"费用: {st['cost_estimate']:.2f}")
        return st

    except Exception as e:
        storage.mark_status(video_url, "failed")
        print(f"  [FAIL] {e}")
        import traceback; traceback.print_exc()
        return None


def _run_all(analyzer, extractor, gb, storage, pp):
    eps = _load_episodes()
    if ALL_RESUME and not ALL_FORCE:
        done = storage.get_completed()
        eps = [e for e in eps if e.get("video_url","") not in done]
        print(f"\n断点续传: 跳过 {len(_load_episodes())-len(eps)} 个, 剩余 {len(eps)}")
    ok = 0
    for ep in eps:
        vu = ep.get("video_url","")
        if not vu: continue
        vp = Path(Config.VIDEO_DIR) / vu
        if not vp.exists(): print(f"  [跳过] {vp}"); continue
        if _analyze_one(vu, str(vp), ep, analyzer, extractor, gb, storage, pp, ALL_FORCE):
            ok += 1
    print(f"\n{ok}/{len(eps)} 成功")


def _run_drama(analyzer, extractor, gb, storage, pp):
    for ep in _load_episodes():
        if DRAMA_NAME not in ep.get("title",""): continue
        vu = ep.get("video_url","")
        vp = Path(Config.VIDEO_DIR) / vu
        if vp.exists():
            _analyze_one(vu, str(vp), ep, analyzer, extractor, gb, storage, pp)


def _run_episode(analyzer, extractor, gb, storage, pp):
    ep = next((e for e in _load_episodes() if e["id"] == EPISODE_ID), None)
    if not ep: print(f"[FATAL] #{EPISODE_ID} 不存在"); return
    vu, vp = ep.get("video_url",""), Path(Config.VIDEO_DIR) / ep.get("video_url","")
    if vp.exists():
        _analyze_one(vu, str(vp), ep, analyzer, extractor, gb, storage, pp)


def _run_single(analyzer, extractor, gb, storage, pp):
    vp = Path(Config.VIDEO_DIR) / SINGLE_VIDEO_URL
    if not vp.exists(): print(f"[FATAL] {vp}"); return
    _analyze_one(SINGLE_VIDEO_URL, str(vp), None, analyzer, extractor, gb, storage, pp)


if __name__ == "__main__":
    main()
