"""
剧集时间轴融合 + 高光检测 + 人物关系图谱
双通道融合：音频(ASR文字+情绪) × 视觉(帧描述+场景变化) → 时间轴 → 高光区间
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import difflib
import networkx as nx


# ═════════════════════════════════════════════════════════════
# 数据结构
# ═════════════════════════════════════════════════════════════

@dataclass
class TimelineSegment:
    """时间轴上的一个片段"""
    start: float
    end: float
    audio_text: str = ""
    audio_speaker: str = ""
    audio_emotion: float = 0.0       # 0-1，LLM判断的音频情绪强度
    visual_description: str = ""
    visual_characters: List[str] = field(default_factory=list)
    visual_change: float = 0.0       # 0-1，与上一帧的画面变化程度
    highlight_score: float = 0.0     # 综合高光得分
    highlight_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "start": self.start,
            "end": self.end,
            "audio_text": self.audio_text,
            "audio_speaker": self.audio_speaker,
            "audio_emotion": self.audio_emotion,
            "visual_description": self.visual_description,
            "visual_characters": self.visual_characters,
            "visual_change": self.visual_change,
            "highlight_score": self.highlight_score,
            "highlight_reasons": self.highlight_reasons,
        }


# ═════════════════════════════════════════════════════════════
# EpisodeTimeline: 单集时间轴融合 + 高光检测
# ═════════════════════════════════════════════════════════════

class EpisodeTimeline:
    """单集时间轴构建器 —— 融合音频层和视觉层"""

    HIGHLIGHT_WEIGHTS = {
        "audio_emotion": 0.35,       # 音频情绪权重
        "visual_change": 0.25,       # 视觉变化权重
        "sync_bonus": 0.20,          # 音视同步加成
        "dialogue_density": 0.15,    # 对话密度
        "trigger_keywords": 0.05,    # 关键词触发
    }

    EMOTION_KEYWORDS = [
        ("爆发", 0.9), ("跪下", 0.85), ("死", 0.9), ("杀", 0.85),
        ("真相", 0.8), ("不可能", 0.75), ("为什么", 0.7), ("站住", 0.7),
        ("滚", 0.7), ("爱", 0.6), ("恨", 0.75), ("求", 0.65),
        ("救命", 0.85), ("住手", 0.8), ("终于", 0.55), ("原来", 0.55),
        ("哈哈哈", 0.5), ("哭", 0.7), ("走", 0.4), ("不", 0.5),
    ]

    def __init__(self, episode_title: str = "", video_url: str = ""):
        self.episode_title = episode_title
        self.video_url = video_url
        self.segments: List[TimelineSegment] = []
        self.highlights: List[Dict] = []

    # ── 构建 ──

    def build(
        self,
        audio_segments: List[Dict],
        frame_analyses: List[Dict],
        frame_interval: float = 5.0,
        video_duration: float = 0
    ) -> List[TimelineSegment]:
        """构建融合时间轴

        Args:
            audio_segments: [{"start","end","text","speaker"}, ...]
            frame_analyses: [{"frame_index","frame_path","scene_description",
                              "characters":[{"name":"..."}], ...}, ...]
            frame_interval: 抽帧间隔（秒）
            video_duration: 视频总时长
        """
        # 1. 音频层 —— 计算每段的情绪强度
        audio_with_emotion = []
        for seg in audio_segments:
            emotion = self._score_audio_emotion(seg.get("text", ""))
            audio_with_emotion.append({
                **seg,
                "emotion": emotion
            })

        # 2. 视觉层 —— 计算相邻帧变化
        frame_with_change = []
        for i, frame in enumerate(frame_analyses):
            ts = frame.get("frame_index", i) * frame_interval
            if i == 0:
                change = 0.0
            else:
                prev_desc = frame_analyses[i-1].get("scene_description", "")
                curr_desc = frame.get("scene_description", "")
                change = self._score_visual_change(prev_desc, curr_desc)

            frame_with_change.append({
                **frame,
                "timestamp": ts,
                "change": change
            })

        # 3. 构建统一时间轴
        segments = self._merge_timeline(
            audio_with_emotion, frame_with_change,
            duration=video_duration
        )

        # 4. 计算高光得分
        self.segments = [self._compute_highlight_score(s) for s in segments]

        # 5. 提取高光区间
        self.highlights = self._extract_highlights(self.segments)

        return self.segments

    # ── 内部方法 ──

    def _score_audio_emotion(self, text: str) -> float:
        """基于关键词和句式判断音频情绪强度"""
        if not text.strip():
            return 0.0

        score = 0.0
        # 关键词匹配
        for kw, weight in self.EMOTION_KEYWORDS:
            if kw in text:
                score = max(score, weight)

        # 标点增强
        if "！" in text or "!" in text:
            score = min(1.0, score + 0.15)
        if "？" in text or "?" in text:
            score = min(1.0, score + 0.1)
        if "..." in text or "……" in text:
            score = min(1.0, score + 0.05)

        # 文本长度缩短 — 短促对话通常情绪更强
        if len(text) <= 5:
            score = min(1.0, score + 0.1)

        return round(score, 2)

    def _score_visual_change(self, prev_desc: str, curr_desc: str) -> float:
        """基于描述文本差异判断视觉变化程度"""
        if not prev_desc or not curr_desc:
            return 0.0

        # 词汇重叠率
        prev_words = set(prev_desc)
        curr_words = set(curr_desc)
        if not curr_words:
            return 0.0
        overlap = len(prev_words & curr_words) / len(curr_words)

        # 变化 = 1 - 重叠率
        change = 1.0 - overlap

        # 场景切换关键词加成
        for kw in ["突然", "切换", "转场", "进入", "离开", "出现", "消失"]:
            if kw in curr_desc:
                change = min(1.0, change + 0.2)
                break

        return round(change, 2)

    def _merge_timeline(
        self,
        audio_segments: List[Dict],
        frame_analyses: List[Dict],
        duration: float = 0
    ) -> List[TimelineSegment]:
        """将音频和视觉数据合并为统一时间轴"""
        if not audio_segments and not frame_analyses:
            return []

        # 找出最晚的结束时间
        max_time = duration
        if audio_segments:
            max_time = max(max_time, max(s.get("end", 0) for s in audio_segments))
        if frame_analyses:
            max_time = max(max_time, max(f.get("timestamp", 0) for f in frame_analyses))

        # 按固定步长（1秒）构建时间轴网格
        step = 1.0
        segments = []
        t = 0.0
        while t < max_time:
            seg = TimelineSegment(start=t, end=t + step)

            # 音频层：找到覆盖当前时间段的对话
            for as_ in audio_segments:
                if as_["start"] <= t < as_["end"]:
                    seg.audio_text = as_.get("text", "")
                    seg.audio_speaker = as_.get("speaker", "")
                    seg.audio_emotion = as_.get("emotion", 0.0)
                    break

            # 视觉层：找到最近的帧描述
            closest_frame = None
            min_dist = float("inf")
            for fa in frame_analyses:
                dist = abs(fa["timestamp"] - t)
                # within 10s of frame considered "close"
                if dist < min_dist and dist <= 10.0:
                    min_dist = dist
                    closest_frame = fa

            if closest_frame:
                seg.visual_description = closest_frame.get("scene_description", "")
                seg.visual_characters = [
                    c.get("name", "") for c in closest_frame.get("characters", [])
                ]
                seg.visual_change = closest_frame.get("change", 0.0)

            segments.append(seg)
            t += step

        return segments

    def _compute_highlight_score(self, seg: TimelineSegment) -> TimelineSegment:
        """综合计算高光得分"""
        w = self.HIGHLIGHT_WEIGHTS

        # 各维度得分
        audio_score = seg.audio_emotion
        visual_score = seg.visual_change

        # 音视同步加成：情绪高 + 画面变化大同时发生
        sync_bonus = audio_score * visual_score  # 两者都高时乘积大

        # 对话密度：有对话则基础分
        dialogue_score = 0.3 if seg.audio_text else 0.0

        # 关键词触发
        kw_score = self._score_keyword_trigger(seg.audio_text)

        score = (
            w["audio_emotion"] * audio_score
            + w["visual_change"] * visual_score
            + w["sync_bonus"] * sync_bonus
            + w["dialogue_density"] * dialogue_score
            + w["trigger_keywords"] * kw_score
        )

        seg.highlight_score = round(score, 3)

        # 记录原因
        reasons = []
        if audio_score >= 0.6:
            reasons.append(f"音频情绪({audio_score:.2f})")
        if visual_score >= 0.4:
            reasons.append(f"画面变化({visual_score:.2f})")
        if sync_bonus >= 0.3:
            reasons.append(f"音视同步({sync_bonus:.2f})")
        if kw_score >= 0.7:
            reasons.append("关键词触发")
        seg.highlight_reasons = reasons

        return seg

    def _score_keyword_trigger(self, text: str) -> float:
        """检测高能关键词"""
        if not text:
            return 0.0
        high_kw = ["跪下", "死", "杀", "救命", "住手", "爆发"]
        for kw in high_kw:
            if kw in text:
                return 0.9
        mid_kw = ["真相", "恨", "滚", "不可能", "哭"]
        for kw in mid_kw:
            if kw in text:
                return 0.7
        return 0.0

    def _extract_highlights(
        self,
        segments: List[TimelineSegment],
        top_k: int = 8,
        merge_gap: float = 10.0,
        min_score: float = 0.15
    ) -> List[Dict]:
        """从时间轴提取高光区间

        Args:
            segments: 时间轴片段列表
            top_k: 最多返回的高光区间数
            merge_gap: 合并间距（秒），小于此值的相邻高光合并
            min_score: 最低高光得分阈值
        """
        if not segments:
            return []

        # 收集所有高于阈值的片段
        candidates = [s for s in segments if s.highlight_score >= min_score]
        if not candidates:
            return []

        # 按得分排序
        candidates.sort(key=lambda s: s.highlight_score, reverse=True)

        # 合并相邻区间
        merged = []
        for seg in candidates:
            if not merged:
                merged.append({
                    "start": seg.start,
                    "end": seg.end,
                    "segments": [seg],
                    "peak_score": seg.highlight_score,
                    "reasons": list(seg.highlight_reasons),
                })
                continue

            last = merged[-1]
            if seg.start - last["end"] <= merge_gap:
                # 合并
                last["end"] = seg.end
                last["segments"].append(seg)
                last["peak_score"] = max(last["peak_score"], seg.highlight_score)
                last["reasons"] = list(set(last["reasons"] + seg.highlight_reasons))
            else:
                merged.append({
                    "start": seg.start,
                    "end": seg.end,
                    "segments": [seg],
                    "peak_score": seg.highlight_score,
                    "reasons": list(seg.highlight_reasons),
                })

        # 按峰值得分排序，取 top_k
        merged.sort(key=lambda h: h["peak_score"], reverse=True)
        highlights = merged[:top_k]

        # 按时间排序输出
        highlights.sort(key=lambda h: h["start"])

        # 清理段引用
        for h in highlights:
            h["reason_text"] = ", ".join(h["reasons"]) if h["reasons"] else "综合得分"
            del h["segments"]

        return highlights

    # ── 输出 ──

    def to_dict(self) -> Dict:
        """导出完整结果"""
        return {
            "episode_title": self.episode_title,
            "video_url": self.video_url,
            "timeline": [s.to_dict() for s in self.segments],
            "highlights": self.highlights,
            "stats": {
                "total_segments": len(self.segments),
                "highlights_count": len(self.highlights),
                "avg_highlight_score": (
                    round(sum(s.highlight_score for s in self.segments) / len(self.segments), 4)
                    if self.segments else 0
                ),
                "peak_highlight": max(
                    (s.highlight_score for s in self.segments), default=0
                )
            }
        }

    def get_highlights_as_percentages(
        self,
        video_duration: float
    ) -> List[float]:
        """返回高光点百分比列表（兼容前端高光标记）"""
        if video_duration <= 0:
            return []
        return [
            round(h["start"] / video_duration * 100, 1)
            for h in self.highlights
        ]


# ═════════════════════════════════════════════════════════════
# GraphBuilder: 人物关系图谱（保持原有接口）
# ═════════════════════════════════════════════════════════════

class GraphBuilder:
    """人物关系图谱构建 - NetworkX"""

    def __init__(self, graph_file: str):
        self.graph_file = Path(graph_file)
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)

    def build_episode_graph(
        self,
        analysis_result: Dict,
        episode_id: str
    ) -> nx.Graph:
        """构建单集人物关系图"""
        G = nx.Graph()
        G.graph["episode_id"] = episode_id

        for char in analysis_result.get("characters", []):
            G.add_node(
                char["id"],
                name=char["name"],
                role=char.get("role", "supporting"),
                description=char.get("description", ""),
                first_appearance=char.get("first_appearance", 0)
            )

        for rel in analysis_result.get("relationships", []):
            G.add_edge(
                rel["source_id"],
                rel["target_id"],
                relation=rel.get("type", "unknown"),
                strength=rel.get("strength", 0.5),
                description=rel.get("description", ""),
                episodes=[episode_id]
            )

        return G

    def merge_global_graph(
        self,
        episode_graph: nx.Graph,
        drama_id: int
    ) -> nx.Graph:
        """将剧集图谱合并到全局图谱"""
        global_graph = self.load_global_graph(drama_id)

        for node, attrs in episode_graph.nodes(data=True):
            if node in global_graph.nodes:
                for key, value in attrs.items():
                    if key not in global_graph.nodes[node]:
                        global_graph.nodes[node][key] = value
                if "episodes" not in global_graph.nodes[node]:
                    global_graph.nodes[node]["episodes"] = []
                ep_id = episode_graph.graph["episode_id"]
                if ep_id not in global_graph.nodes[node]["episodes"]:
                    global_graph.nodes[node]["episodes"].append(ep_id)
            else:
                global_graph.add_node(
                    node, **attrs,
                    episodes=[episode_graph.graph["episode_id"]]
                )

        for u, v, attrs in episode_graph.edges(data=True):
            if global_graph.has_edge(u, v):
                existing_episodes = global_graph.edges[u, v].get("episodes", [])
                ep_id = episode_graph.graph["episode_id"]
                if ep_id not in existing_episodes:
                    existing_episodes.append(ep_id)
                    global_graph.edges[u, v]["episodes"] = existing_episodes
                if attrs.get("strength", 0) > global_graph.edges[u, v].get("strength", 0):
                    global_graph.edges[u, v]["strength"] = attrs["strength"]
            else:
                global_graph.add_edge(u, v, **attrs)

        return global_graph

    def load_global_graph(self, drama_id: int) -> nx.Graph:
        """加载全局图谱"""
        if not self.graph_file.exists():
            G = nx.Graph()
            G.graph["drama_id"] = drama_id
            return G
        with open(self.graph_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return nx.node_link_graph(data)

    def save_global_graph(self, graph: nx.Graph):
        """保存全局图谱"""
        data = nx.node_link_data(graph)
        with open(self.graph_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"图谱已保存到: {self.graph_file}")
        print(f"  - 节点数: {graph.number_of_nodes()}")
        print(f"  - 边数: {graph.number_of_edges()}")

    def get_character_network(
        self, character_id: str, depth: int = 2
    ) -> Dict:
        """获取指定人物的社交网络"""
        graph = self.load_global_graph(1)
        if character_id not in graph:
            return {"error": f"人物 {character_id} 不存在"}
        neighbors = nx.single_source_shortest_path_length(
            graph, character_id, cutoff=depth
        )
        subgraph = graph.subgraph(neighbors.keys())
        return nx.node_link_data(subgraph)

    def get_character_info(self, character_id: str) -> Optional[Dict]:
        """获取人物详细信息"""
        graph = self.load_global_graph(1)
        if character_id not in graph:
            return None
        node_data = dict(graph.nodes[character_id])
        neighbors = list(graph.neighbors(character_id))
        relationships = []
        for neighbor in neighbors:
            edge_data = graph.edges[character_id, neighbor]
            relationships.append({
                "character_id": neighbor,
                "character_name": graph.nodes[neighbor].get("name", neighbor),
                "relation": edge_data.get("relation", "unknown"),
                "strength": edge_data.get("strength", 0.5),
                "description": edge_data.get("description", ""),
                "episodes": edge_data.get("episodes", [])
            })
        node_data["relationships"] = relationships
        node_data["connection_count"] = len(neighbors)
        return node_data


    # ── 人物名称聚类 ──

    # 称呼前缀/后缀（剥离后比较核心名）
    HONORIFIC_PREFIXES = ["小", "老", "阿"]
    HONORIFIC_SUFFIXES = ["哥", "总", "老板", "大人", "姑娘", "姐", "爷", "少", "先生", "女士", "夫人"]

    @classmethod
    def _strip_honorifics(cls, name: str) -> str:
        """剥离称呼前后缀，返回核心名（保护2字以上结果）"""
        core = name
        # 剥离前缀（小张→张，阿明→明）
        for pfx in cls.HONORIFIC_PREFIXES:
            if core.startswith(pfx) and len(core) - len(pfx) >= 1:
                core = core[len(pfx):]
                break
        # 剥离后缀（三哥→三，林姑娘→林姑娘而非林）
        for sfx in cls.HONORIFIC_SUFFIXES:
            if core.endswith(sfx) and len(core) - len(sfx) >= 1:
                core = core[:-len(sfx)]
                break
        return core if len(core) >= 1 else name

    @classmethod
    def cluster_character_names(
        cls,
        names: List[str],
        auto_merge_threshold: float = 0.6
    ) -> Dict[str, str]:
        """人物名称聚类去重

        规则(优先级从高到低):
        1. 完全相同 → 直接合并
        2. 剥离称呼(小/老/阿/哥/总/大人等)后核心名相同 → 合并
        3. 核心名字串包含 (核心名A 包含 核心名B) → 合并为较长者(全名)
        4. 编辑距离 > threshold → 合并
        5. 同姓双名 vs 同姓双名 → 不合并(可能不同人)

        Returns:
            {"三哥":"张三","张三哥":"张三","张三":"张三"}
        """
        if len(names) <= 1:
            return {n: n for n in names}

        unique = list(dict.fromkeys(names))
        canonical = {n: n for n in unique}

        for i, name_a in enumerate(unique):
            for j, name_b in enumerate(unique):
                if i >= j:
                    continue
                if canonical[name_a] != name_a or canonical[name_b] != name_b:
                    continue

                # 规则1: 完全相同 (已去重, skip)

                # 规则2: 剥离称呼后核心名相同 → 选较短者作基名
                core_a = cls._strip_honorifics(name_a)
                core_b = cls._strip_honorifics(name_b)
                if core_a == core_b:
                    # 较短的是基名（"张三" 优于 "张三哥"）
                    canonical_name = name_a if len(name_a) <= len(name_b) else name_b
                    canonical[name_a] = canonical_name
                    canonical[name_b] = canonical_name
                    continue

                # 规则3: 核心名字串包含
                # 保护: 2字名是独立人名，不合并到同名开头的3字名（张伟≠张伟强）
                skip_substr = False
                if len(core_a) == 2 and core_b.startswith(core_a) and len(core_b) >= 3:
                    skip_substr = True
                if len(core_b) == 2 and core_a.startswith(core_b) and len(core_a) >= 3:
                    skip_substr = True
                if not skip_substr:
                    if core_a in core_b:
                        canonical[name_a] = name_b
                        canonical[name_b] = name_b
                        continue
                    if core_b in core_a:
                        canonical[name_b] = name_a
                        canonical[name_a] = name_a
                        continue

                # 规则4: 编辑距离
                similarity = difflib.SequenceMatcher(None, core_a, core_b).ratio()
                if similarity >= auto_merge_threshold:
                    # 规则5: 同姓不同名保护
                    # 5a: 同姓双名 vs 同姓双名 → skip (张伟明≠张伟强)
                    if len(core_a) >= 2 and len(core_b) >= 2:
                        if core_a[:2] == core_b[:2] and len(core_a) >= 3 and len(core_b) >= 3:
                            continue
                    # 5b: 2字名 vs 以它开头的长名 → skip (张伟≠张伟强)
                    if len(core_a) == 2 and core_b.startswith(core_a) and len(core_b) >= 3:
                        continue
                    if len(core_b) == 2 and core_a.startswith(core_b) and len(core_a) >= 3:
                        continue
                    canonical_name = name_a if len(name_a) <= len(name_b) else name_b
                    canonical[name_a] = canonical_name
                    canonical[name_b] = canonical_name

        return canonical


    @staticmethod
    def cluster_with_llm(
        names: List[str],
        api_key: str,
        base_url: str,
        model: str = "doubao-1.5-pro-32k"
    ) -> Dict[str, str]:
        """LLM辅助的角色名聚类（处理规则无法判定的别名）

        用于规则聚类后仍有歧义的名称对，如:
        "王总" vs "王建国" — 可能是同一个人（总=尊称），也可能不是
        """
        if len(names) <= 1:
            return {n: n for n in names}

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)

        prompt = f"""你是一位短剧分析师。判断以下角色名列表中哪些是同一个人。

角色名列表: {json.dumps(names, ensure_ascii=False)}

规则:
- "X哥"/"X总"/"X老板" 等称呼 通常 = "X" 本人
- "张伟" 和 "张伟强" 是不同人（不同全名）
- "小X" 通常 = "X" 本人

输出JSON映射，把别名映射到规范名:
{{"别名1":"规范名", "别名2":"规范名"}}
只输出需要合并的别名，不需要合并的不输出。
只输出JSON。"""

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            content = resp.choices[0].message.content
            # Extract JSON
            start = content.find('{')
            if start >= 0:
                end = content.rfind('}') + 1
                return json.loads(content[start:end])
        except Exception:
            pass

        return {}
    def merge_characters_by_cluster(
        self,
        characters: List[Dict],
        cluster_map: Dict[str, str]
    ) -> List[Dict]:
        """根据聚类映射合并人物列表

        Args:
            characters: [{"id":"char_001","name":"张三哥",...}]
            cluster_map: {"张三哥":"张三", "三哥":"张三", ...}

        Returns:
            合并后的人物列表（同名人物取第一次出现的属性）
        """
        merged = {}
        for char in characters:
            name = char.get("name", "")
            canonical_name = cluster_map.get(name, name)
            if canonical_name not in merged:
                merged[canonical_name] = {
                    **char,
                    "name": canonical_name,
                    "aliases": [name] if name != canonical_name else []
                }
            else:
                if name != canonical_name and name not in merged[canonical_name]["aliases"]:
                    merged[canonical_name]["aliases"].append(name)
        return list(merged.values())

    def export_to_d3_json(self, drama_id: int) -> Dict:
        """导出为D3.js可用的JSON格式"""
        graph = self.load_global_graph(drama_id)
        nodes = []
        for node_id, attrs in graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": attrs.get("name", node_id),
                "role": attrs.get("role", "supporting"),
                "description": attrs.get("description", ""),
                "episodes": attrs.get("episodes", []),
                "group": 1 if attrs.get("role") == "protagonist" else 2
            })
        links = []
        for u, v, attrs in graph.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "relation": attrs.get("relation", "unknown"),
                "strength": attrs.get("strength", 0.5)
            })
        return {"nodes": nodes, "links": links}
