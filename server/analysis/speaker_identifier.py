"""
ASR驱动的人物识别模块
通过音频分析定位说话人时间轴 → 精准抽帧 → VL识别 → spk→角色映射
解决跨剧情角色对齐的核心模块
"""
import os
import json
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from config import Config
from video_preprocessor import VideoPreprocessor
from multimodal_analyzer import MultimodalAnalyzer


class SpeakerIdentifier:
    """ASR驱动的说话人识别器 — 双通道策略的核心"""

    def __init__(
        self,
        analyzer: MultimodalAnalyzer,
        preprocessor: VideoPreprocessor,
        frame_dir: str
    ):
        self.analyzer = analyzer
        self.preprocessor = preprocessor
        self.frame_dir = Path(frame_dir)
        self.frame_dir.mkdir(parents=True, exist_ok=True)

    def identify_speakers_for_episode(
        self,
        video_path: str,
        video_url: str,
        audio_result: Dict,
        context_characters: Optional[List[Dict]] = None
    ) -> Dict:
        """
        对单集进行ASR驱动的说话人识别

        Args:
            video_path: 视频文件绝对路径
            video_url: 视频URL标识
            audio_result: audio_analyzer.analyze_full() 的返回结果
            context_characters: 本集场景分析中已知的人物列表（可选，用于提示VL）

        Returns:
            {
                "video_url": "xxx",
                "speaker_map": {"spk0": "张三", "spk1": "李四", ...},
                "identifications": [
                    {"speaker": "spk0", "character": "张三", "confidence": 0.9, "timestamp": 45.2},
                    ...
                ]
            }
        """
        dialogue = audio_result.get("dialogue", [])
        if not dialogue:
            print("[SpeakerIdentifier] 无对话数据，跳过")
            return {"video_url": video_url, "speaker_map": {}, "identifications": []}

        # Group by speaker
        speaker_segments = defaultdict(list)
        for seg in dialogue:
            spk = seg.get("speaker", "unknown")
            speaker_segments[spk].append(seg)

        episode_dir = self.frame_dir / video_url.replace("/", "_").replace("\\", "_")
        episode_dir.mkdir(parents=True, exist_ok=True)

        identifications = []
        speaker_map = {}

        for spk, segments in speaker_segments.items():
            # Pick the longest segment for best VL accuracy
            best_seg = max(segments, key=lambda s: s.get("end", 0) - s.get("start", 0))
            mid_ts = (best_seg["start"] + best_seg["end"]) / 2

            # Extract frame at midpoint
            frame_name = f"spk_{spk}_{mid_ts:.1f}s.jpg"
            frame_path = str(episode_dir / frame_name)

            try:
                self.preprocessor.extract_frame_at_timestamp(
                    video_path, frame_path, mid_ts
                )

                # VL identify speaker
                result = self.analyzer.identify_speaker(
                    frame_path,
                    context_characters=context_characters
                )

                char_name = result.get("speaker_name", "unknown")
                confidence = result.get("confidence", 0.0)

                if char_name != "unknown" and confidence > 0.3:
                    speaker_map[spk] = char_name
                    identifications.append({
                        "speaker": spk,
                        "character": char_name,
                        "confidence": confidence,
                        "timestamp": mid_ts,
                        "evidence": result.get("evidence", ""),
                        "frame_path": frame_path
                    })
                    print(f"  [SpeakerIdentifier] {spk} -> {char_name} "
                          f"(confidence={confidence:.2f}, @{mid_ts:.1f}s)")
                else:
                    print(f"  [SpeakerIdentifier] {spk} -> unknown "
                          f"(confidence={confidence:.2f}, keeping as {spk})")

                time.sleep(0.3)  # Rate limit

            except Exception as e:
                print(f"  [SpeakerIdentifier] {spk} 识别失败: {e}")

        return {
            "video_url": video_url,
            "speaker_map": speaker_map,
            "identifications": identifications
        }

    def merge_cross_episode_speakers(
        self,
        all_episode_results: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        跨剧集合并说话人映射

        规则：多集中同一个角色名映射到不同spk -> 记录为别名
              spk0在第3集=张三, spk2在第5集=张三 -> 张三同时关联spk0和spk2

        Args:
            all_episode_results: [ep1_result, ep2_result, ...]

        Returns:
            {"张三": ["spk0", "spk2"], "李四": ["spk1"]}
        """
        char_to_spks = defaultdict(set)

        for ep_result in all_episode_results:
            for spk, char in ep_result.get("speaker_map", {}).items():
                char_to_spks[char].add(spk)

        result = {char: sorted(spks) for char, spks in char_to_spks.items()}

        print(f"[SpeakerIdentifier] 跨集合并结果:")
        for char, spks in result.items():
            print(f"  {char}: {spks}")

        return result

    def save_to_file(self, data: Dict, output_path: str):
        """保存识别结果到文件"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing if any
        existing = {}
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # Merge: update episode results
        video_url = data["video_url"]
        existing[video_url] = data

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        print(f"[SpeakerIdentifier] 结果已保存到 {output_path}")

    def load_from_file(self, output_path: str) -> Dict:
        """从文件加载识别结果"""
        if not Path(output_path).exists():
            return {}
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
