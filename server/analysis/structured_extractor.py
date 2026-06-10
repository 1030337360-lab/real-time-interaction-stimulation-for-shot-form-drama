"""
结构化信息提取模块 - LLM总结
统一使用 OpenAI 兼容接口，支持通义千问 / 豆包
"""
import json
import time
import re
from typing import List, Dict, Optional
from openai import OpenAI


class StructuredExtractor:
    """结构化信息提取 - 基于 LLM (OpenAI 兼容接口)"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=300.0
        )
        print(f"[StructuredExtractor] 初始化完成，模型: {self.model}")

    def extract_summary(
        self,
        frame_analyses: List[dict],
        episode_title: str = "",
        viewer_context: str = ""
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

{viewer_context}
帧分析:
{analyses_text}

请提取:
1. 人物列表（包含首次出现时间戳）
2. 人物关系（关系类型和强度）
3. 关键场景 — 满足以下任一条件即为剧情转折:
   - 新人物登场: 重要角色首次出场
   - 信息揭露: 秘密/真相/身份被揭开
   - 关系变化: 结盟/背叛/决裂/和解
   - 冲突爆发: 争吵/打斗/对峙达到顶点
   - 命运转折: 获得/失去重要物品或权力
   - 悬念设置: 每集结尾的cliffhanger
   importance: critical(本集核心转折) / high(重要推进) / medium(铺垫) / low(过渡)
4. 本集摘要（100字）

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
      "importance": "critical(本集核心转折)|high(重要推进)|medium(铺垫)|low(过渡)",
      "emotional_impact": 9
    }}
  ],
  "highlights_auto": [75, 140, 200]
}}

只输出JSON，不要其他内容。"""

        result = self._call_llm(prompt)

        try:
            # Extract first complete JSON object (brace-counting)
            json_start = result.find('{')
            if json_start >= 0:
                brace_count = 0
                json_end = json_start
                for k in range(json_start, len(result)):
                    if result[k] == '{':
                        brace_count += 1
                    elif result[k] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = k + 1
                            break
                try:
                    json_match = json.loads(result[json_start:json_end])
                except json.JSONDecodeError:
                    json_match = None
            else:
                json_match = None
            if json_match is not None:
                return json_match
            else:
                return {"error": f"无法解析LLM响应: {result}"}
        except Exception as e:
            return {"error": f"解析错误: {e}"}

    def _call_llm(self, prompt: str) -> str:
        """调用LLM API (OpenAI兼容接口)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.7
        )

        return response.choices[0].message.content


    def score_visual_intensity(
        self,
        frame_analyses: List[dict]
    ) -> List[dict]:
        """LLM对每帧的画面表现强度打分 (0-5)

        基于帧描述文本判断——不需要图像，LLM凭文本理解能力评分。
        返回: [{"frame_index":0, "intensity":3, "reason":"..."}, ...]
        """
        if not frame_analyses:
            return []

        # 构建每帧的描述摘要
        frame_lines = []
        for i, fa in enumerate(frame_analyses):
            desc = fa.get("scene_description", fa.get("场景描述", ""))
            chars = fa.get("characters", fa.get("出现的人物", []))
            char_text = ""
            if isinstance(chars, list) and chars:
                names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in chars[:3]]
                char_text = f" 人物: {', '.join(names)}"
            elif isinstance(chars, str):
                char_text = f" 人物: {chars[:60]}"
            frame_lines.append(f"[帧{i+1}] {desc[:120]}{char_text}")

        frames_text = "\n".join(frame_lines)

        prompt = f"""你是一位影视分析专家。对以下每一帧的画面表现强度打分(0-5)。

评分标准:
0分-空镜/过渡: 纯景物、空房间、风景、转场镜头。例: "古风建筑外景，悬挂匾额"
1分-静态存在: 人物在场但无动作无情绪，静态站立/坐。例: "室内，男子静坐桌旁，面无表情"
2分-日常活动: 走路、行礼、端茶、交谈等日常行为。例: "男子从门外走进，拱手行礼"
3分-情绪表达: 有明显情绪反应：哭泣、大笑、震惊、愤怒表情。例: "男子双眼圆睁嘴巴大张，神态满是错愕"
4分-冲突对抗: 对峙、争吵、打斗、拔剑、推搡、威胁。例: "两人拔剑对峙，气氛紧张一触即发"
5分-极致冲突: 伤亡、爆炸、毁灭、重大揭示、跪地痛哭。例: "女子倒在血泊中，男子跪地痛哭"

帧分析:
{frames_text}

对每一帧，先一句话分析画面内容，再打分。输出JSON数组:
[{{"frame_index":0,"intensity":3,"analysis":"一句话分析","evidence":"引用原文关键描述"}}, ...]
只输出JSON数组，不要其他内容。"""

        result = self._call_llm(prompt)

        # 解析
        import json as _json
        json_start = result.find('[')
        if json_start >= 0:
            brace_count = 0
            json_end = json_start
            for k in range(json_start, len(result)):
                if result[k] == '[':
                    brace_count += 1
                elif result[k] == ']':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = k + 1
                        break
            try:
                scores = _json.loads(result[json_start:json_end])
                # 补齐 frame_index
                for j, s in enumerate(scores):
                    if "frame_index" not in s:
                        s["frame_index"] = j
                print(f"[VisualIntensity] {len(scores)} 帧评分完成, "
                      f"均分={sum(s.get('intensity',0) for s in scores)/len(scores):.1f}")
                return scores
            except (_json.JSONDecodeError, ValueError) as e:
                print(f"[VisualIntensity] 解析失败: {e}")

        return [{"frame_index": i, "intensity": 0, "analysis": "parse failed"}
                for i in range(len(frame_analyses))]
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
      "importance": "critical(本集核心转折)|high(重要推进)|medium(铺垫)|low(过渡)",
      "emotional_impact": 8
    }}
  ]
}}

只输出JSON。"""

        result = self._call_llm(prompt)

        try:
            # Extract first complete JSON object (brace-counting)
            json_start = result.find('{')
            if json_start >= 0:
                brace_count = 0
                json_end = json_start
                for k in range(json_start, len(result)):
                    if result[k] == '{':
                        brace_count += 1
                    elif result[k] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = k + 1
                            break
                try:
                    json_match = json.loads(result[json_start:json_end])
                except json.JSONDecodeError:
                    json_match = None
            else:
                json_match = None
            if json_match is not None:
                return json_match
            else:
                return {"error": f"无法解析LLM响应: {result}"}
        except Exception as e:
            return {"error": f"解析错误: {e}"}
