"""
人物-说话人对齐模块 - 关联视觉中的人物与音频中的说话人
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class CharacterSpeakerAligner:
    """人物-说话人对齐器"""

    def __init__(self, llm_api_key: str, llm_url: str, llm_model: str = "qwen-plus"):
        from openai import OpenAI
        self.api_key = llm_api_key
        self.api_url = llm_url
        self.llm_model = llm_model
        self.client = OpenAI(api_key=llm_api_key, base_url=llm_url, timeout=60.0)

    def _get_speaker_at_time(
        self,
        dialogue_list: List[Dict],
        target_time: float
    ) -> Optional[str]:
        """根据时间点找到对应的说话人"""
        for dia in dialogue_list:
            start = dia.get("start", 0)
            end = dia.get("end", 999999)
            if start <= target_time <= end:
                return dia.get("speaker")
        return None

    def _get_speakers_in_window(
        self,
        dialogue_list: List[Dict],
        time_start: float,
        time_end: float
    ) -> List[str]:
        """获取某时间窗口内所有出现的说话人"""
        speakers = set()
        for dia in dialogue_list:
            s_start = dia.get("start", 0)
            s_end = dia.get("end", 999999)
            if not (s_end < time_start or s_start > time_end):
                spk = dia.get("speaker")
                if spk:
                    speakers.add(spk)
        return sorted(list(speakers))

    def align_character_speakers(
        self,
        visual_analysis: Dict,
        dialogue_list: List[Dict],
        frame_interval_seconds: int = 5
    ) -> Dict:
        """
        核心对齐函数：把视觉中出现的人物与音频中的spkN关联起来

        Args:
            visual_analysis: 视频分析结果（含characters列表）
            dialogue_list: ASR得到的带speaker的对话列表
            frame_interval_seconds: 抽帧间隔（秒）

        Returns:
            speaker_to_char: {'spk0': '张三', 'spk1': '李四', ...}
        """
        characters = visual_analysis.get("characters", [])
        char_names = [c.get("name", "") for c in characters if c.get("name")]

        if not char_names or not dialogue_list:
            print("[Aligner] 缺少人物或对话，跳过对齐")
            return {}

        print(f"[Aligner] 开始对齐：{len(char_names)} 个人物 ↔ {len(dialogue_list)} 条对话")
        print(f"  人物列表: {char_names}")

        frame_windows = []
        for i, char in enumerate(characters):
            first_appear = char.get("first_appearance", i * frame_interval_seconds * 2)
            time_window = (
                max(0, first_appear - frame_interval_seconds),
                first_appear + frame_interval_seconds * 2
            )
            frame_windows.append({
                "char_name": char.get("name", str(char)),
                "time_window": time_window,
                "possible_speakers": self._get_speakers_in_window(
                    dialogue_list,
                    time_window[0],
                    time_window[1]
                )
            })

        print(f"  人物时间窗口分析完成: {frame_windows}")

        mapping = self._llm_align(
            characters=char_names,
            frame_windows=frame_windows,
            full_dialogue=dialogue_list
        )

        print(f"[Aligner] 对齐结果: {mapping}")
        return mapping

    def _llm_align(
        self,
        characters: List[str],
        frame_windows: List[Dict],
        full_dialogue: List[Dict]
    ) -> Dict[str, str]:
        """
        使用LLM推理得到最终的spkN到人物名的映射
        """
        if len(characters) == 0 or len(full_dialogue) == 0:
            return {}

        windows_text = "\n".join([
            f"- {w['char_name']} 首次出现在 {w['time_window']} 秒范围内，此时可能说话人: {w['possible_speakers']}"
            for w in frame_windows
        ])

        dialogue_text = "\n".join([
            f"[{d['speaker']} @ {d['start']:.1f}s] {d['text']}"
            for d in full_dialogue[:30]
        ])

        prompt = f"""你是一位专业的短剧内容分析师。根据以下信息，把音频中的说话人ID映射到真实人物名。

【已知人物列表】
{', '.join(characters)}

【人物首次出现时间与可能说话人】
{windows_text}

【部分对话片段】（按时间排序）
{dialogue_text}

任务：
建立从spk0/spk1/spk2... 到 真实人物名 的映射关系。
优先规则：
1. 某人物首次出现的时间窗口内，只有1个说话人，直接映射
2. 结合对话内容推理谁在说话（比如对话是主角说的，就映射到主角）

输出JSON格式：
{{
  "spk0": "张三",
  "spk1": "李四"
}}
只输出JSON，不要其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.3
            )
            content = response.choices[0].message.content

            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                mapping = json.loads(json_match.group(0))
                return mapping
            else:
                print(f"  ⚠ LLM返回格式不对，使用降级对齐")
                return self._fallback_align(characters, full_dialogue)

        except Exception as e:
            print(f"  ⚠ LLM对齐异常: {e}，使用降级对齐")
            return self._fallback_align(characters, full_dialogue)

    def _fallback_align(self, characters: List[str], full_dialogue: List[Dict]) -> Dict[str, str]:
        """
        简单降级策略：直接按顺序一一对应
        spk0 -> 人物1, spk1 -> 人物2 ...
        """
        mapping = {}
        unique_speakers = sorted(list({d["speaker"] for d in full_dialogue if "speaker" in d}))
        for i, spk in enumerate(unique_speakers):
            if i < len(characters):
                mapping[spk] = characters[i]
            else:
                mapping[spk] = f"未知人物{i}"
        print(f"  [降级对齐] 简单映射: {mapping}")
        return mapping

    def apply_mapping_to_dialogue(
        self,
        dialogue_list: List[Dict],
        speaker_to_character: Dict[str, str]
    ) -> List[Dict]:
        """应用对齐映射，把对话中的spkN替换成真实人名"""
        result = []
        for dia in dialogue_list:
            new_dia = dict(dia)
            original_spk = dia.get("speaker", "")
            if original_spk in speaker_to_character:
                new_dia["speaker_real_name"] = speaker_to_character[original_spk]
            result.append(new_dia)
        return result
