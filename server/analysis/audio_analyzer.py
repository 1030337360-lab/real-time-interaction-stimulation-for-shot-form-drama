"""
音频分析模块 - 基于 FunASR
功能：音频提取、VAD人声检测、ASR语音识别、说话人分离、环境音分类
"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import torch


class AudioSegment:
    """音频片段数据结构"""
    def __init__(
        self,
        start: float,
        end: float,
        text: str = "",
        speaker: str = "",
        audio_type: str = "speech"
    ):
        self.start = start
        self.end = end
        self.text = text
        self.speaker = speaker
        self.audio_type = audio_type  # speech / music / effect / silence

    def to_dict(self) -> Dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "speaker": self.speaker,
            "audio_type": self.audio_type,
            "duration": self.end - self.start
        }


class AudioAnalyzer:
    """完整音频分析器 - 所有模型在初始化时加载"""

    def __init__(
        self,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        download_dir: Optional[str] = None
    ):
        self.device = device
        self.download_dir = download_dir
        self._models_loaded = False

        self.vad_model = None
        self.asr_model = None
        self.spk_model = None
        self.sound_classifier = None

        print(f"[AudioAnalyzer] 初始化，设备: {self.device}")

    def load_models(self):
        """预加载所有模型"""
        if self._models_loaded:
            print("[AudioAnalyzer] 模型已加载，跳过")
            return

        print("[AudioAnalyzer] 开始加载FunASR模型...")

        try:
            from funasr import AutoModel

            model_kwargs = {
                "device": self.device,
            }
            if self.download_dir:
                model_kwargs["download_dir"] = self.download_dir

            print("  [1/4] 加载 VAD (人声检测)...")
            self.vad_model = AutoModel(
                model="fsmn-vad",
                model_revision="v2.0.4",
                **model_kwargs
            )

            print("  [2/4] 加载 ASR (语音识别 Paraformer)...")
            self.asr_model = AutoModel(
                model="paraformer-zh",
                model_revision="v2.0.4",
                **model_kwargs
            )

            print("  [3/4] 加载 说话人分离 CAM++...")
            self.spk_model = AutoModel(
                model="campplus-cmn",
                model_revision="v2.0.0",
                **model_kwargs
            )

            print("  [4/4] 加载 环境音分类 PANNs...")
            try:
                self.sound_classifier = AutoModel(
                    model="panns-cnn14-audioset",
                    model_revision="v1.0.0",
                    **model_kwargs
                )
            except Exception as e:
                print(f"  ⚠ PANNs加载失败，跳过环境音分类: {e}")

            self._models_loaded = True
            print("[AudioAnalyzer] 所有模型加载完成!")

        except ImportError as e:
            raise RuntimeError(
                "请先安装依赖: pip install funasr modelscope torch\n"
                f"错误详情: {e}"
            )

    def extract_audio_from_video(
        self,
        video_path: str,
        output_audio_path: Optional[str] = None
    ) -> str:
        """从视频提取音频 (WAV格式 16kHz mono)"""
        video_path = Path(video_path)

        if output_audio_path is None:
            temp_dir = tempfile.gettempdir()
            output_audio_path = str(
                Path(temp_dir) / f"{video_path.stem}_audio.wav"
            )

        output_path = Path(output_audio_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(output_path),
            "-y"
        ]

        print(f"[AudioAnalyzer] 提取音频: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"音频提取失败: {result.stderr}")

        print(f"[AudioAnalyzer] 音频已保存: {output_path}")
        return str(output_path)

    def detect_speech_segments(
        self,
        audio_path: str,
        max_segment_duration: float = 30.0
    ) -> List[Tuple[float, float]]:
        """VAD检测人声片段，返回 (start, end) 时间戳列表"""
        if not self.vad_model:
            self.load_models()

        result = self.vad_model.generate(input=audio_path)
        segments = result[0]["value"]

        speech_segments = []
        for seg in segments:
            start_sec = seg[0] / 1000  # VAD输出毫秒
            end_sec = seg[1] / 1000

            duration = end_sec - start_sec
            if duration > max_segment_duration:
                num_parts = int(duration // max_segment_duration) + 1
                part_dur = (end_sec - start_sec) / num_parts
                for i in range(num_parts):
                    speech_segments.append((
                        start_sec + i * part_dur,
                        start_sec + (i + 1) * part_dur
                    ))
            else:
                speech_segments.append((start_sec, end_sec))

        print(f"[AudioAnalyzer] VAD检测到 {len(speech_segments)} 个人声片段")
        return speech_segments

    def transcribe_speech(
        self,
        audio_path: str,
        segments: Optional[List[Tuple[float, float]]] = None
    ) -> List[AudioSegment]:
        """ASR语音识别，返回带时间戳的文本"""
        if not self.asr_model:
            self.load_models()

        if segments is None:
            segments = self.detect_speech_segments(audio_path)

        results = []
        for i, (start, end) in enumerate(segments):
            print(f"  ASR处理片段 {i+1}/{len(segments)}: {start:.1f}s - {end:.1f}s")

            try:
                result = self.asr_model.generate(
                    input=audio_path,
                    batch_size_s=end - start,
                    time_stamp=True
                )

                text = result[0]["text"] if result else ""
                results.append(AudioSegment(
                    start=start,
                    end=end,
                    text=text,
                    audio_type="speech"
                ))
            except Exception as e:
                print(f"  ⚠ 片段识别失败: {e}")
                results.append(AudioSegment(
                    start=start,
                    end=end,
                    text="",
                    audio_type="speech"
                ))

        return results

    def diarize_speakers(
        self,
        audio_path: str,
        speech_segments: List[AudioSegment]
    ) -> List[AudioSegment]:
        """说话人分离，给每个片段分配speaker ID"""
        if not self.spk_model:
            print("[AudioAnalyzer] 跳过说话人分离，模型未加载")
            for seg in speech_segments:
                seg.speaker = "spk0"
            return speech_segments

        print("[AudioAnalyzer] 执行说话人分离...")
        try:
            result = self.spk_model.generate(
                input=audio_path,
                batch_size_s=300
            )
            spk_info = result[0] if result else {}

            # Try to use actual diarization result; fall back to round-robin
            spk_labels = spk_info.get("spk", []) if spk_info else []
            for i, seg in enumerate(speech_segments):
                if i < len(spk_labels):
                    seg.speaker = f"spk{spk_labels[i]}"
                else:
                    seg.speaker = f"spk{i % 4}"

            print(f"[AudioAnalyzer] 说话人分离完成")

        except Exception as e:
            print(f"  ⚠ 说话人分离失败: {e}，使用默认spk0")
            for seg in speech_segments:
                seg.speaker = "spk0"

        return speech_segments

    def classify_audio_types(
        self,
        audio_path: str,
        all_segments: List[Tuple[float, float, str]]
    ) -> List[AudioSegment]:
        """对非人声片段进行环境音分类"""
        results = []

        if not self.sound_classifier:
            print("[AudioAnalyzer] 跳过环境音分类，模型未加载")
            for start, end, audio_type in all_segments:
                results.append(AudioSegment(start, end, audio_type=audio_type))
            return results

        print("[AudioAnalyzer] 环境音分类...")
        for i, (start, end, _) in enumerate(all_segments):
            try:
                result = self.sound_classifier.generate(
                    input=audio_path,
                    batch_size_s=end - start
                )
                top_label = result[0]["labels"][0] if result else "unknown"

                audio_type = "other"
                if "music" in top_label.lower():
                    audio_type = "music"
                elif "effect" in top_label.lower() or "sound" in top_label.lower():
                    audio_type = "effect"
                elif "silence" in top_label.lower():
                    audio_type = "silence"

                results.append(AudioSegment(
                    start=start,
                    end=end,
                    audio_type=audio_type
                ))
            except Exception as e:
                results.append(AudioSegment(start, end, audio_type="other"))

        print(f"[AudioAnalyzer] 分类完成")
        return results

    def analyze_full(
        self,
        video_path: str,
        output_audio_path: Optional[str] = None
    ) -> Dict:
        """完整分析流程"""
        print(f"\n{'='*60}")
        print(f"音频全流程分析: {Path(video_path).name}")
        print(f"{'='*60}")

        if not self._models_loaded:
            self.load_models()

        audio_path = self.extract_audio_from_video(video_path, output_audio_path)

        speech_ts = self.detect_speech_segments(audio_path)
        speech_segments = self.transcribe_speech(audio_path, speech_ts)
        speech_segments = self.diarize_speakers(audio_path, speech_segments)

        all_segments = [seg.to_dict() for seg in speech_segments]

        dialogue_list = [
            {
                "speaker": seg["speaker"],
                "text": seg["text"],
                "start": seg["start"],
                "end": seg["end"]
            }
            for seg in all_segments
            if seg["audio_type"] == "speech" and seg["text"]
        ]

        result = {
            "video_path": video_path,
            "audio_path": audio_path,
            "total_speech_segments": len(speech_segments),
            "dialogue": dialogue_list,
            "segments": all_segments
        }

        print(f"\n✓ 音频分析完成!")
        print(f"  人声片段: {len(speech_segments)}")
        print(f"  有效对话: {len(dialogue_list)} 句")

        return result
