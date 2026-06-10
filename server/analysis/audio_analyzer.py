"""
音频分析模块 - 基于 FunASR
功能：音频提取、VAD人声检测、ASR语音识别、说话人分离、环境音分类
完全兼容无GPU环境，模型加载失败时自动优雅降级
新增：超强防卡住机制 + 超时控制 + 详细进度日志
"""
import os
import sys
import time
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import torch


class TimeoutException(Exception):
    """超时异常"""
    pass


def run_with_timeout(func, args=(), kwargs=None, timeout=300):
    """带超时保护的函数执行器"""
    if kwargs is None:
        kwargs = {}
    
    result_container = {"result": None, "exception": None}
    
    def wrapper():
        try:
            result_container["result"] = func(*args, **kwargs)
        except Exception as e:
            result_container["exception"] = e
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        raise TimeoutException(f"操作超时（{timeout}秒）")
    if result_container["exception"] is not None:
        raise result_container["exception"]
    return result_container["result"]


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
        download_dir: Optional[str] = None,
        timeout_seconds: int = 600
    ):
        self.device = device
        self.download_dir = download_dir
        self.timeout_seconds = timeout_seconds
        self._models_loaded = False
        self._available = False
        self._loading_progress = 0

        self.vad_model = None
        self.asr_model = None
        self.spk_model = None
        self.sound_classifier = None

        print(f"[AudioAnalyzer] 初始化，设备: {self.device}, 总超时: {timeout_seconds}秒")

    def is_available(self) -> bool:
        """检查音频分析是否可用"""
        return self._available

    def _safe_generate(self, model, input_data, **kwargs):
        """安全调用模型 generate，防止卡住"""
        print(f"  -> 模型调用开始... (input类型: {type(input_data)})")
        start_t = time.time()
        result = model.generate(input=input_data, **kwargs)
        elapsed = time.time() - start_t
        print(f"  -> 模型调用完成，耗时 {elapsed:.1f}秒")
        return result

    def load_models(self):
        """预加载所有模型 - 使用经典公开模型组合 + 防卡住"""
        if self._models_loaded:
            print("[AudioAnalyzer] 模型已加载，跳过")
            return

        print("[AudioAnalyzer] " + "="*50)
        print("[AudioAnalyzer] 开始加载FunASR模型...")
        print(f"[AudioAnalyzer] Python版本: {sys.version}")
        print(f"[AudioAnalyzer] PyTorch版本: {torch.__version__}")
        print("[AudioAnalyzer] " + "="*50)

        try:
            import warnings
            warnings.filterwarnings("ignore", category=ImportWarning)
            import logging
            
            # 把所有funasr相关日志级别调到WARNING，减少噪音
            for name in ['funasr', 'modelscope', 'torch']:
                logging.getLogger(name).setLevel(logging.WARNING)
            
            from funasr import AutoModel

            self._loading_progress = 1
            print("[AudioAnalyzer]  [1/4] 加载 VAD (fsmn-vad)...")
            sys.stdout.flush()
            self.vad_model = AutoModel(
                model="fsmn-vad",
                model_revision="v2.0.4",
                device=self.device,
                disable_update=True
            )
            print("[AudioAnalyzer]  [1/4] VAD 加载成功!")
            sys.stdout.flush()

            self._loading_progress = 2
            print("[AudioAnalyzer]  [2/4] 加载 ASR (paraformer-zh)...")
            sys.stdout.flush()
            self.asr_model = AutoModel(
                model="paraformer-zh",
                model_revision="v2.0.4",
                device=self.device,
                disable_update=True
            )
            print("[AudioAnalyzer]  [2/4] ASR 加载成功!")
            sys.stdout.flush()

            self._loading_progress = 3
            print("[AudioAnalyzer]  [3/4] 加载 说话人分离 (campplus-cmn)...")
            sys.stdout.flush()
            try:
                self.spk_model = AutoModel(
                    model="CAMPPlus",
                    model_revision="v2.0.0",
                    device=self.device,
                    disable_update=True
                )
                print("[AudioAnalyzer]  [3/4] 说话人分离 加载成功!")
            except Exception as e:
                print(f"[AudioAnalyzer]  ⚠ 说话人分离模型加载失败，跳过: {type(e).__name__}: {e}")
                self.spk_model = None
            sys.stdout.flush()

            self._loading_progress = 4
            print("[AudioAnalyzer]  [4/4] 环境音分类 (可选)...")
            sys.stdout.flush()
            try:
                self.sound_classifier = AutoModel(
                    model="CAMPPlus",

                    device=self.device,
                    disable_update=True
                )
                print("[AudioAnalyzer]  [4/4] 环境音分类 加载成功!")
            except Exception as e:
                print(f"[AudioAnalyzer]  ⚠ 环境音分类模型加载失败，跳过: {type(e).__name__}: {e}")
                self.sound_classifier = None
            sys.stdout.flush()

            self._models_loaded = True
            self._available = (self.vad_model is not None and self.asr_model is not None)
            print("[AudioAnalyzer] " + "="*50)
            print("[AudioAnalyzer] ✅ 所有核心模型加载完成!")
            print(f"[AudioAnalyzer]    VAD: {'✅' if self.vad_model else '❌'}")
            print(f"[AudioAnalyzer]    ASR: {'✅' if self.asr_model else '❌'}")
            print(f"[AudioAnalyzer]    说话人分离: {'✅' if self.spk_model else '❌'}")
            print(f"[AudioAnalyzer]    环境音分类: {'✅' if self.sound_classifier else '❌'}")
            print("[AudioAnalyzer] " + "="*50)

        except ImportError as e:
            print(f"[AudioAnalyzer] ⚠ FunASR未安装，音频分析功能将完全跳过: {e}")
            print("[AudioAnalyzer]    提示: 请运行 pip install funasr modelscope torch torchaudio")
            self._models_loaded = True
            self._available = False
        except Exception as e:
            print(f"[AudioAnalyzer] ⚠ 模型加载部分失败，音频分析将以有限模式运行: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self._models_loaded = True
            self._available = (self.vad_model is not None and self.asr_model is not None)

    def extract_audio_from_video(
        self,
        video_path: str,
        output_audio_path: Optional[str] = None
    ) -> str:
        """从视频提取音频 (WAV格式 16kHz mono) - 带进度日志"""
        video_path = Path(video_path)
        print(f"[AudioAnalyzer] 开始提取音频从: {video_path.name}")

        if output_audio_path is None:
            temp_dir = tempfile.gettempdir()
            output_audio_path = str(
                Path(temp_dir) / f"{video_path.stem}_{int(time.time())}_audio.wav"
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
            "-y",
            str(output_path),
        ]

        print(f"[AudioAnalyzer] 执行 FFmpeg 音频提取...")
        sys.stdout.flush()
        
        # 不带 text=True，避免大输出阻塞
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            encoding='utf-8',
            errors='ignore',
            timeout=300  # 音频提取最多5分钟
        )

        if result.returncode != 0:
            print(f"[AudioAnalyzer] FFmpeg stderr (前500字符): {result.stderr[:500]}")
            raise RuntimeError(f"音频提取失败，返回码: {result.returncode}")

        if not output_path.exists() or output_path.stat().st_size < 1000:
            raise RuntimeError(f"音频文件太小或不存在: {output_path}")

        print(f"[AudioAnalyzer] ✅ 音频提取完成: {output_path.name} ({output_path.stat().st_size/1024/1024:.1f} MB)")
        return str(output_path)

    def detect_speech_segments(
        self,
        audio_path: str,
        max_segment_duration: float = 30.0
    ) -> List[Tuple[float, float]]:
        """VAD检测人声片段，返回 (start, end) 时间戳列表"""
        if not self.vad_model:
            if not self._models_loaded:
                self.load_models()
            if not self.vad_model:
                print("[AudioAnalyzer] VAD模型不可用，返回模拟片段")
                return [(0.0, 300.0)]

        try:
            print("[AudioAnalyzer] 开始VAD人声检测...")
            result = self._safe_generate(self.vad_model, audio_path)
            segments = result[0]["value"] if result and len(result) > 0 else []
            print(f"[AudioAnalyzer] VAD原始输出得到 {len(segments)} 个片段")

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

            print(f"[AudioAnalyzer] ✅ VAD检测到 {len(speech_segments)} 个人声片段")
            return speech_segments
        except Exception as e:
            print(f"[AudioAnalyzer] ⚠ VAD检测失败: {type(e).__name__}: {e}，返回模拟片段")
            import traceback
            traceback.print_exc()
            return [(0.0, 300.0)]

    def transcribe_speech(
        self,
        audio_path: str,
        segments: Optional[List[Tuple[float, float]]] = None
    ) -> List[AudioSegment]:
        """ASR语音识别，返回带时间戳的文本"""
        if not self.asr_model:
            if not self._models_loaded:
                self.load_models()
            if not self.asr_model:
                print("[AudioAnalyzer] ASR模型不可用，返回空结果")
                return []

        if segments is None:
            segments = self.detect_speech_segments(audio_path)

        # 逐VAD片段裁剪音频并单独ASR识别
        import tempfile
        import subprocess as _sp
        results = []
        total_seg = len(segments)

        for i, (start, end) in enumerate(segments):
            seg_dur = end - start
            if seg_dur <= 0.1:
                continue

            print(f"[AudioAnalyzer]  ASR片段 {i+1}/{total_seg}: {start:.1f}s - {end:.1f}s (时长{seg_dur:.1f}s)")
            sys.stdout.flush()

            # 裁剪该片段为临时音频文件
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            try:
                cmd = [
                    "ffmpeg", "-ss", str(start), "-t", str(seg_dur),
                    "-i", audio_path, "-vn", "-ar", "16000", "-ac", "1",
                    "-acodec", "pcm_s16le", tmp.name, "-y", "-loglevel", "error"
                ]
                _sp.run(cmd, check=True, capture_output=True)

                result = self.asr_model.generate(
                    input=tmp.name,
                    batch_size_s=min(seg_dur, 60),
                )
                text = result[0].get("text", "") if result else ""
                results.append(AudioSegment(start=start, end=end, text=text.strip(), audio_type="speech"))
                if text.strip():
                    print(f"    -> {text[:80]}{'...' if len(text) > 80 else ''}")
            except Exception as e:
                print(f"    ⚠ 失败: {type(e).__name__}: {e}")
                results.append(AudioSegment(start=start, end=end, text="", audio_type="speech"))
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

        print(f"[AudioAnalyzer] ✅ ASR完成: {len(results)} 个片段, "
              f"{sum(1 for r in results if r.text.strip())} 个有文本")
        return results

    def diarize_speakers(
        self,
        audio_path: str,
        speech_segments: List[AudioSegment]
    ) -> List[AudioSegment]:
        """说话人分离，给每个片段分配speaker ID"""
        if not self.spk_model:
            print("[AudioAnalyzer] 跳过说话人分离，模型未加载，使用默认spk0")
            for seg in speech_segments:
                seg.speaker = "spk0"
            return speech_segments

        print("[AudioAnalyzer] 执行说话人分离...")
        try:
            result = self._safe_generate(self.spk_model, audio_path, batch_size_s=300)
            spk_info = result[0] if result and len(result) > 0 else {}

            spk_labels = spk_info.get("spk", []) if spk_info else []
            for i, seg in enumerate(speech_segments):
                if i < len(spk_labels):
                    seg.speaker = f"spk{spk_labels[i]}"
                else:
                    seg.speaker = f"spk{i % 4}"

            print(f"[AudioAnalyzer] ✅ 说话人分离完成")

        except Exception as e:
            print(f"  ⚠ 说话人分离失败: {type(e).__name__}: {e}，使用默认spk0")
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
                result = self._safe_generate(self.sound_classifier, audio_path, batch_size_s=end - start)
                top_label = result[0]["labels"][0] if result and len(result) > 0 else "unknown"

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

        print(f"[AudioAnalyzer] ✅ 分类完成")
        return results

    def analyze_full(
        self,
        video_path: str,
        output_audio_path: Optional[str] = None
    ) -> Dict:
        """完整分析流程 - 失败时返回空的有效结构，不崩溃，全程防卡住"""
        print(f"\n{'='*70}")
        print(f"[AudioAnalyzer] 音频全流程分析: {Path(video_path).name}")
        print(f"{'='*70}")

        try:
            if not self._models_loaded:
                self.load_models()

            if not self._available:
                print("[AudioAnalyzer] ⚠ 音频分析不可用，返回空结果")
                return {
                    "video_path": video_path,
                    "audio_path": "",
                    "total_speech_segments": 0,
                    "dialogue": [],
                    "segments": [],
                    "skipped": True,
                    "reason": "audio_analyzer_not_available"
                }

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
                "segments": all_segments,
                "skipped": False
            }

            print(f"\n{'='*70}")
            print(f"[AudioAnalyzer] ✅ 音频分析全部完成!")
            print(f"  - 人声片段总数: {len(speech_segments)}")
            print(f"  - 有效对话数: {len(dialogue_list)} 句")
            print(f"{'='*70}")

            return result

        except Exception as e:
            print(f"[AudioAnalyzer] ❌ 音频分析整体失败，返回空结构，流程将继续...")
            print(f"  错误类型: {type(e).__name__}")
            print(f"  错误信息: {e}")
            import traceback
            traceback.print_exc()
            return {
                "video_path": video_path,
                "audio_path": "",
                "total_speech_segments": 0,
                "dialogue": [],
                "segments": [],
                "error": str(e),
                "error_type": type(e).__name__,
                "skipped": True,
                "reason": "exception_in_analyze_full"
            }
