"""
结果存储模块 - 独立JSON文件存储，按video_url作为key
"""
import json
from pathlib import Path
from typing import Optional, Dict


class AnalysisStorage:
    """分析结果存储 - 使用独立文件，video_url作为key"""

    def __init__(self, json_path: str):
        self.path = Path(json_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self._init_empty_db()

    def _init_empty_db(self):
        """初始化空数据库"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    def _load_data(self) -> Dict:
        """加载JSON数据"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self._init_empty_db()
            return {}

    def _save_data(self, data: Dict):
        """保存JSON数据"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update_episode_analysis(
        self,
        video_url: str,
        analysis_result: Dict
    ):
        """
        更新剧集的AI分析结果

        Args:
            video_url: 视频URL路径（如"天下第一纨绔/第1集.mp4"）
            analysis_result: 分析结果
        """
        data = self._load_data()
        data[video_url] = {
            "ai_analysis": analysis_result,
            "updated_at": analysis_result.get("analyzed_at", "")
        }
        self._save_data(data)
        print(f"已更新 {video_url} 的分析结果")

    def get_episode_analysis(self, video_url: str) -> Optional[Dict]:
        """获取剧集分析结果"""
        data = self._load_data()
        entry = data.get(video_url)
        if entry:
            return entry.get("ai_analysis")
        return None

    def has_analysis(self, video_url: str) -> bool:
        """检查剧集是否有分析结果"""
        data = self._load_data()
        return video_url in data

    def delete_analysis(self, video_url: str):
        """删除剧集分析结果"""
        data = self._load_data()
        if video_url in data:
            del data[video_url]
            self._save_data(data)
            print(f"已删除 {video_url} 的分析结果")

    def get_all_video_urls(self) -> list:
        """获取所有已分析的video_url"""
        data = self._load_data()
        return list(data.keys())

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        data = self._load_data()
        total_analyses = len(data)

        total_characters = 0
        total_scenes = 0

        for entry in data.values():
            ai = entry.get("ai_analysis", {})
            total_characters += len(ai.get("characters", []))
            total_scenes += len(ai.get("key_scenes", []))

        return {
            "total_analyses": total_analyses,
            "total_characters": total_characters,
            "total_key_scenes": total_scenes
        }
