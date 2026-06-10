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
MODE = "drama"

# MODE="all": 分析 drama.json 中所有剧集
ALL_RESUME = True     # 断点续传, 跳过已完成
ALL_FORCE = False     # 强制重跑全部

# MODE="drama": 分析指定剧名的所有集
DRAMA_NAME = "北派寻宝笔记"  # "天下第一纨绔"

# MODE="episode": 分析指定ID的剧集
EPISODE_ID = 1

# MODE="single": 分析单个视频文件
SINGLE_VIDEO_URL = "北派寻宝笔记/第63集.mp4" # "天下第一纨绔/第2集.mp4"

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

import sys, json, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from video_preprocessor import VideoPreprocessor
from multimodal_analyzer import MultimodalAnalyzer
from structured_extractor import StructuredExtractor
from graph_builder import GraphBuilder, EpisodeTimeline, ViewerContext
from storage import AnalysisStorage


def main():
    # 命令行参数覆盖顶部配置（供 watcher 调用）
    import argparse as _ap
    _parser = _ap.ArgumentParser(description="短剧AI分析")
    _parser.add_argument("--mode", choices=["all","drama","episode","single"], default=None)
    _parser.add_argument("--drama", type=str, default=None)
    _parser.add_argument("--video-url", type=str, default=None)
    _parser.add_argument("--episode", type=int, default=None)
    _parser.add_argument("--force", action="store_true")
    _parser.add_argument("--resume", action="store_true")
    _parser.add_argument("--no-audio", action="store_true")
    _args, _ = _parser.parse_known_args()

    global MODE, DRAMA_NAME, SINGLE_VIDEO_URL, EPISODE_ID, ALL_FORCE, ALL_RESUME, ENABLE_AUDIO
    if _args.mode: MODE = _args.mode
    if _args.drama: DRAMA_NAME = _args.drama
    if _args.video_url: SINGLE_VIDEO_URL = _args.video_url
    if _args.episode: EPISODE_ID = _args.episode
    if _args.force: ALL_FORCE = True
    if _args.resume: ALL_RESUME = True
    if _args.no_audio: ENABLE_AUDIO = False

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
    # 按剧名分文件存储图谱
    gb_drama = DRAMA_NAME if MODE == "drama" else None
    graph_builder = GraphBuilder(Config.GRAPH_FILE, drama_name=gb_drama)
    # 按剧名分文件存储
    drama_for_storage = DRAMA_NAME if MODE == "drama" else None
    storage = AnalysisStorage(Config.ANALYSIS_RESULTS_PATH, drama_name=drama_for_storage)
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
                 graph_builder, storage, preprocessor, force=False,
                 viewer_context=None):
    """分析单集完整流程"""
    print(f"\n{'='*60}")
    print(f"  {video_url}")
    print(f"{'='*60}")

    if not force:
        if storage.get_status(video_url) == "completed":
            c = storage.get_episode_analysis(video_url)
            if c:
                print("  [跳过] 已完成"); return c, viewer_context

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
        # 增量保存断点，每分析一帧立即写入
        checkpoint = str(
            Path(Config.OUTPUT_DIR)
            / f"frames_checkpoint_{video_url.replace('/', '_').replace(chr(92), '_')}.json"
        )
        frame_analyses = analyzer.analyze_frames_batch(
            frames, delay=0.5, checkpoint_path=checkpoint
        )

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

        # 4. 结构化（先跑，拿到LLM识别的剧情转折）
        print("  [4/5] LLM提取...")
        vc_text = viewer_context.to_prompt_context() if viewer_context else ""
        st = extractor.extract_summary(
            frame_analyses,
            Path(video_path).parent.name,
            viewer_context=vc_text
        )

        # 4.5 LLM画面表现强度评分
        print("  [4.5/5] 画面强度评分...")
        visual_intensity = extractor.score_visual_intensity(frame_analyses)

        # 5. 时间轴（注入LLM剧情转折 + LLM画面强度）
        print("  [5/5] 时间轴融合...")
        dur = preprocessor._get_duration(video_path)
        tl = EpisodeTimeline(Path(video_path).parent.name, video_url)
        tl.build(audio_segments, frame_analyses, Config.FRAME_INTERVAL_SECONDS, dur,
                 key_scenes=st.get("key_scenes", []),
                 visual_intensity=visual_intensity)

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
        episode_frame_dir = Path(Config.FRAME_DIR) / video_url.replace("/", "_").replace("\\", "_")
        episode_frame_dir.mkdir(parents=True, exist_ok=True)
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
                st["speaker_identifications"] = r.get("identifications", [])

                # 表情帧: 每个说话人时间点前后1s各抽1帧
                print("  [附加] 说话人表情分析...")
                expr_scores = []
                for ident in r.get("identifications", []):
                    ts = ident.get("timestamp", 0)
                    for offset in (-1, 0, 1):
                        t = max(0, ts + offset)
                        frame_name = f"expr_{ident['speaker']}_{t:.1f}s.jpg"
                        fp = str(episode_frame_dir / frame_name) if 'episode_frame_dir' in dir() else str(Path(Config.FRAME_DIR) / frame_name)
                        try:
                            preprocessor.extract_frame_at_timestamp(video_path, fp, t)
                            res = analyzer.analyze_expression(fp)
                            expr_scores.append({
                                "frame_index": len(expr_scores),
                                "timestamp": t,
                                "intensity": res.get("intensity", 0),
                                "speaker": ident.get("character", ident.get("speaker", "")),
                                "emotion": res.get("emotion", ""),
                                "evidence": res.get("evidence", "")
                            })
                            print(f"    表情 @{t:.1f}s: {res.get('intensity',0)}分 {res.get('emotion','')}")
                            time.sleep(0.3)
                        except Exception as ex:
                            pass

                # 合并表情分到 visual_intensity
                if expr_scores:
                    visual_intensity.extend(expr_scores)
            except Exception as e:
                print(f"  [警告] {e}")

        # 同步高光点到后端
        _sync_highlights_to_backend(video_url, st)

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

        # 更新观众知识
        if viewer_context is not None:
            viewer_context.update_from_episode(
                characters=st.get("characters", []),
                key_scenes=st.get("key_scenes", []),
                summary=st.get("summary", ""),
                episode_title=Path(video_path).parent.name
            )

        print(f"  [OK] 人物:{len(st.get('characters',[]))} 高光:{len(st['highlights_auto'])} "
              f"费用: {st['cost_estimate']:.2f}")
        return st, viewer_context

    except Exception as e:
        storage.mark_status(video_url, "failed")
        print(f"  [FAIL] {e}")
        import traceback; traceback.print_exc()
        return None


def _sync_highlights_to_backend(video_url: str, st: dict):
    """将高光推送到 Express 后端 /internal/highlights (只推 top-1 interval)"""
    highlights = st.get("highlights_auto", [])
    intervals = st.get("highlight_intervals", [])

    # 从 drama.json 查找 episode_id
    try:
        with open(Config.LOWDB_PATH, "r", encoding="utf-8") as f:
            episodes = json.load(f).get("episodes", [])
        ep = next((e for e in episodes if e.get("video_url") == video_url), None)
        if not ep:
            return
        episode_id = ep["id"]
    except Exception as e:
        print(f"  [高光同步] 查找 episode_id 失败: {e}")
        return

    # intervals: 只取 top-1 最高分区间，超过60s居中截断
    video_dur = st.get("video_duration", 300)
    MAX_HIGHLIGHT_SEC = 60
    mapped_intervals = []
    if intervals:
        best = max(intervals, key=lambda h: h.get("peak_score", 0))
        start_s = best.get("start", 0)
        end_s = best.get("end", start_s + 5)
        if end_s - start_s > MAX_HIGHLIGHT_SEC:
            center = (start_s + end_s) / 2
            start_s = max(0, center - MAX_HIGHLIGHT_SEC / 2)
            end_s = min(video_dur, center + MAX_HIGHLIGHT_SEC / 2)
        mapped_intervals = [{
            "start": round(start_s, 1),
            "end": round(end_s, 1),
            "start_percent": round(start_s / video_dur * 100, 1) if video_dur > 0 else 0,
            "end_percent": round(end_s / video_dur * 100, 1) if video_dur > 0 else 0,
            "title": best.get("reason_text", "") or "高光时刻",
            "description": best.get("reason_text", ""),
            "importance": "high" if best.get("peak_score", 0) > 0.4 else "medium",
            "tags": [t.strip() for t in best.get("reason_text", "").split(",") if t.strip()]
        }]

    # points: 取区间中点百分比
    points = []
    if mapped_intervals:
        mid_pct = (mapped_intervals[0]["start_percent"] + mapped_intervals[0]["end_percent"]) / 2
        points = [round(mid_pct, 1)]

    if not mapped_intervals:
        return

    # POST 到后端
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "episode_id": episode_id,
            "points": points,
            "intervals": mapped_intervals
        }).encode("utf-8")
        req = _ur.Request(
            "http://localhost:3001/internal/highlights",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = _ur.urlopen(req, timeout=10)
        body = json.loads(resp.read())
        print(f"  [高光同步] episode={episode_id} "
              f"point={points[0] if points else '?'}  → {resp.status}")
    except Exception as e:
        print(f"  [高光同步] POST 失败 (后端未启动?): {e}")
def _run_all(analyzer, extractor, gb, storage, pp):
    eps = _load_episodes()
    if ALL_RESUME and not ALL_FORCE:
        done = storage.get_completed()
        eps = [e for e in eps if e.get("video_url","") not in done]
        print(f"\n断点续传: 跳过 {len(_load_episodes())-len(eps)} 个, 剩余 {len(eps)}")

    # 观众知识上下文（模拟观看体验，前集信息注入后集分析）
    viewer_ctx = ViewerContext()
    ok = 0
    for ep in eps:
        vu = ep.get("video_url","")
        if not vu: continue
        vp = Path(Config.VIDEO_DIR) / vu
        if not vp.exists(): print(f"  [跳过] {vp}"); continue
        result = _analyze_one(vu, str(vp), ep, analyzer, extractor, gb, storage, pp, ALL_FORCE,
                              viewer_context=viewer_ctx)
        if result:
            st, vc = result
            if vc is not None:
                viewer_ctx = vc
            ok += 1
            # 每集结束: 缓存刷盘 + 释放内存
            if analyzer.cache:
                analyzer.cache.flush_and_release()
            import gc
            gc.collect()
    print(f"\n{ok}/{len(eps)} 成功")


def _run_drama(analyzer, extractor, gb, storage, pp):
    """分析指定剧的所有集，按集数从小到大 + 观众视角上下文积累"""
    import re

    # 筛选 + 排序
    eps = [e for e in _load_episodes() if DRAMA_NAME in e.get("video_url", "")]
    if not eps:
        print(f"[FATAL] 未找到剧名包含 '{DRAMA_NAME}' 的剧集")
        return

    # 从 filename 中提取集数排序: "第63集.mp4" → 63
    def episode_num(ep):
        vu = ep.get("video_url", "") or ep.get("filename", "")
        m = re.search(r'第(\d+)集', vu)
        return int(m.group(1)) if m else 0

    eps.sort(key=episode_num)
    print(f"\n剧集: {DRAMA_NAME} ({len(eps)} 集, 第{episode_num(eps[0])}-{episode_num(eps[-1])}集)")
    print(f"观众视角: 前集信息将注入后续分析\n")


    # 观众上下文
    viewer_ctx = ViewerContext()
    ok = 0
    for i, ep in enumerate(eps):
        vu = ep.get("video_url", "")
        vp = Path(Config.VIDEO_DIR) / vu
        if not vp.exists():
            print(f"  [跳过] 文件不存在: {vp}")
            continue

        print(f"\n{'#'*50}")
        print(f"  [{episode_num(ep)}/{episode_num(eps[-1])}] 第{episode_num(ep)}集")
        print(f"{'#'*50}")

        result = _analyze_one(vu, str(vp), ep, analyzer, extractor, gb, storage, pp,
                              force=ALL_FORCE, viewer_context=viewer_ctx)
        if result:
            st, vc = result
            if vc is not None:
                viewer_ctx = vc
            ok += 1
            # 每集结束: 缓存刷盘 + 释放内存
            if analyzer.cache:
                analyzer.cache.flush_and_release()
            import gc
            gc.collect()

    print(f"\n{DRAMA_NAME}: {ok}/{len(eps)} 集完成")


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
