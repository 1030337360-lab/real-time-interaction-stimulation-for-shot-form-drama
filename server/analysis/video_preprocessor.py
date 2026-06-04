"""
视频预处理模块 - FFmpeg封装
"""
import os
import subprocess
from pathlib import Path
from typing import List, Tuple


class VideoPreprocessor:
    """视频预处理 - FFmpeg封装"""

    def __init__(self, frame_dir: str):
        self.frame_dir = Path(frame_dir)
        self.frame_dir.mkdir(parents=True, exist_ok=True)

    def extract_key_frames(
        self,
        video_path: str,
        output_dir: str,
        num_frames: int = 30
    ) -> List[str]:
        """
        提取关键帧（按总视频时长均匀分配）

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            num_frames: 要提取的帧数

        Returns:
            帧文件路径列表
        """
        video_path = Path(video_path)
        episode_name = video_path.stem
        episode_dir = Path(output_dir) / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        duration = self._get_duration(video_path)

        interval = max(1, int(duration / num_frames))

        output_pattern = str(episode_dir / "frame_%03d.jpg")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            "-frames:v", str(num_frames),
            output_pattern,
            "-y"
        ]

        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg错误: {result.stderr}")
            raise RuntimeError(f"抽帧失败: {result.stderr}")

        frames = sorted(episode_dir.glob("frame_*.jpg"))
        print(f"提取了 {len(frames)} 帧到 {episode_dir}")

        return [str(f) for f in frames]

    def extract_fixed_interval_frames(
        self,
        video_path: str,
        output_dir: str,
        interval_seconds: int = 5
    ) -> List[str]:
        """
        按固定时间间隔截取帧（每interval_seconds秒一帧）

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            interval_seconds: 截取间隔（秒，默认5秒）

        Returns:
            帧文件路径列表
        """
        video_path = Path(video_path)
        episode_name = video_path.stem
        episode_dir = Path(output_dir) / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        output_pattern = str(episode_dir / "frame_%03d.jpg")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval_seconds}",
            "-q:v", "2",
            output_pattern,
            "-y"
        ]

        print(f"[固定间隔抽帧] 每{interval_seconds}秒一帧，执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg错误: {result.stderr}")
            raise RuntimeError(f"抽帧失败: {result.stderr}")

        frames = sorted(episode_dir.glob("frame_*.jpg"))
        print(f"固定间隔抽帧完成，共提取 {len(frames)} 帧（每{interval_seconds}秒一帧）")

        return [str(f) for f in frames]

    def extract_key_frames_smart(
        self,
        video_path: str,
        output_dir: str,
        num_frames: int = 30
    ) -> List[str]:
        """
        智能提取关键帧（基于场景切换检测）

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            num_frames: 要提取的帧数

        Returns:
            帧文件路径列表
        """
        video_path = Path(video_path)
        episode_name = video_path.stem
        episode_dir = Path(output_dir) / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        output_pattern = str(episode_dir / "scene_%03d.jpg")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"select='gt(scene,0.3)',fps=1/{max(1, 300//num_frames)}",
            "-q:v", "2",
            "-frames:v", str(num_frames),
            output_pattern,
            "-y"
        ]

        print(f"执行场景切换检测抽帧: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg场景检测错误，fallback到普通抽帧: {result.stderr}")
            return self.extract_key_frames(video_path, output_dir, num_frames)

        frames = sorted(episode_dir.glob("scene_*.jpg"))
        if len(frames) < 5:
            print(f"场景切换检测帧数不足({len(frames)})，fallback到普通抽帧")
            return self.extract_key_frames(video_path, output_dir, num_frames)

        print(f"通过场景切换检测提取了 {len(frames)} 帧")
        return [str(f) for f in frames]

    def _get_duration(self, video_path: str) -> float:
        """获取视频时长（秒）"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except (ValueError, subprocess.CalledProcessError):
            print(f"获取视频时长失败: {result.stderr}")
            return 300.0

    def extract_audio(self, video_path: str, output_path: str) -> str:
        """提取音频（用于ASR，可选）"""
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_path,
            "-y"
        ]
        subprocess.run(cmd, capture_output=True)
        return output_path

    def get_video_info(self, video_path: str) -> dict:
        """获取视频详细信息"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        import json
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"获取视频信息失败: {result.stderr}")
            return {}


    def extract_frame_at_timestamp(
        self,
        video_path: str,
        output_path: str,
        timestamp_seconds: float
    ) -> str:
        """在指定时间戳提取单帧"""
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp_seconds),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
            "-y"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"指定时间戳抽帧失败 ({timestamp_seconds}s): {result.stderr}")
        return output_path


    def cleanup_temp_audio(self, audio_path: str):
        """清理临时音频文件"""
        import os as _os
        audio = Path(audio_path)
        if audio.exists():
            audio.unlink()
            print(f"已清理临时音频: {audio_path}")

    def cleanup_frames(self, episode_dir: str):
        """清理指定剧集的帧文件"""
        import shutil
        episode_path = Path(episode_dir)
        if episode_path.exists():
            shutil.rmtree(episode_path)
            print(f"已清理帧目录: {episode_path}")
