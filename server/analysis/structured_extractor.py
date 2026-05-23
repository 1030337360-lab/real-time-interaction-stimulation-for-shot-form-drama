"""
结构化信息提取模块 - LLM总结
"""
import json
import requests
import time
import re
from typing import List, Dict, Optional


class StructuredExtractor:
    """结构化信息提取 - 基于LLM"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    def extract_summary(
        self,
        frame_analyses: List[dict],
        episode_title: str = ""
    ) -> dict:
        """
        从帧分析结果中提取结构化信息

        Args:
            frame_analyses: 帧分析结果列表
            episode_title: 剧集标题

        Returns:
            结构化提取结果
        """
        valid_analyses = [a for a in frame_analyses if "error" not in a]

        if not valid_analyses:
            return {"error": "没有有效的帧分析结果"}

        analyses_text = "\n".join([
            f"[帧{i+1}] {a.get('scene_description', '')} | "
            f"人物: {', '.join([c.get('name', '') for c in a.get('characters', [])])} | "
            f"关键事件: {a.get('key_event', '无')}"
            for i, a in enumerate(valid_analyses[:30])
        ])

        prompt = f"""你是一个专业的短剧分析师。根据以下剧集帧分析，提取结构化信息。

剧集: {episode_title}

帧分析:
{analyses_text}

请提取:
1. 人物列表（包含首次出现时间戳）
2. 人物关系（关系类型和强度）
3. 关键场景（高能时刻）
4. 本集摘要

输出JSON格式:
{{
  "summary": "本集摘要（100字内）",
  "characters": [
    {{
      "id": "char_001",
      "name": "人物名",
      "role": "protagonist|antagonist|supporting",
      "first_appearance": 0,
      "description": "人物描述"
    }}
  ],
  "relationships": [
    {{
      "source_id": "char_001",
      "target_id": "char_002",
      "type": "关系类型",
      "strength": 0.8,
      "description": "关系描述"
    }}
  ],
  "key_scenes": [
    {{
      "frame_index": 15,
      "timestamp": 75,
      "title": "场景标题",
      "description": "场景描述",
      "importance": "critical|high|medium|low",
      "emotional_impact": 9
    }}
  ],
  "highlights_auto": [75, 140, 200]
}}

只输出JSON，不要其他内容。"""

        result = self._call_llm(prompt)

        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": f"无法解析LLM响应: {result}"}
        except Exception as e:
            return {"error": f"解析错误: {e}"}

    def _call_llm(self, prompt: str, model: str = "qwen-plus") -> str:
        """调用LLM API"""
        payload = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "result_format": "message"
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.api_url, json=payload, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"LLM API调用失败: {response.text}")

        result = response.json()

        try:
            return result["output"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"解析LLM响应失败: {str(e)}, 原始响应: {result}")

    def map_to_highlights(
        self,
        key_scenes: List[dict],
        video_duration: float
    ) -> List[float]:
        """
        将关键场景映射为高光点时间戳

        Args:
            key_scenes: 关键场景列表
            video_duration: 视频总时长（秒）

        Returns:
            高光点时间戳列表
        """
        if not key_scenes:
            return []

        highlights = []

        for scene in key_scenes:
            importance = scene.get("importance", "medium")
            emotional = scene.get("emotional_impact", 5)

            if importance in ["critical", "high"] or emotional >= 7:
                frame_index = scene.get("frame_index", 0)
                interval = max(1, video_duration / 30)
                timestamp = frame_index * interval

                highlights.append(timestamp)

        highlights.sort()
        return highlights

    def extract_from_text(
        self,
        text_description: str,
        episode_title: str = ""
    ) -> dict:
        """
        从文本描述中提取结构化信息（备用方法）

        Args:
            text_description: 文本描述
            episode_title: 剧集标题

        Returns:
            结构化提取结果
        """
        prompt = f"""你是一个专业的短剧分析师。根据以下剧集描述，提取结构化信息。

剧集: {episode_title}

描述:
{text_description}

请提取JSON格式:
{{
  "summary": "本集摘要",
  "characters": [
    {{
      "id": "char_001",
      "name": "人物名",
      "role": "protagonist|antagonist|supporting",
      "description": "人物描述"
    }}
  ],
  "relationships": [
    {{
      "source_id": "char_001",
      "target_id": "char_002",
      "type": "关系类型",
      "strength": 0.8,
      "description": "关系描述"
    }}
  ],
  "key_scenes": [
    {{
      "title": "场景标题",
      "description": "场景描述",
      "importance": "critical|high|medium|low",
      "emotional_impact": 8
    }}
  ]
}}

只输出JSON。"""

        result = self._call_llm(prompt)

        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": f"无法解析LLM响应: {result}"}
        except Exception as e:
            return {"error": f"解析错误: {e}"}
