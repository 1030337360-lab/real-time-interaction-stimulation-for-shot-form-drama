"""
多模态分析模块 - 统一OpenAI兼容接口
支持：通义千问 / 豆包 Doubao-Seed-2.0-lite
"""
import base64
import time
import re
from pathlib import Path
from typing import List, Dict, Optional

from openai import OpenAI
import json

import hashlib


class FrameCache:
    """帧分析结果缓存 — SHA256帧哈希 + 模型名 作为键"""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "frame_cache.json"
        self._data = None

    def _load(self) -> dict:
        if self._data is None:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        return self._data

    def _save(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def flush_and_release(self):
        """写回磁盘并释放内存中的 dict"""
        if self._data is not None:
            self._save()
            self._data = None

    def clear(self):
        """清空所有缓存（内存 + 磁盘）"""
        self._data = {}
        self._save()

    @staticmethod
    def hash_frame(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def get(self, frame_path: str, model: str, tag: str = "scene") -> dict | None:
        """tag 区分分析目的: scene / speaker / ... 防止不同类型覆盖"""
        key = f"{self.hash_frame(frame_path)}:{model}:{tag}"
        return self._load().get(key)

    def set(self, frame_path: str, model: str, result: dict, tag: str = "scene"):
        key = f"{self.hash_frame(frame_path)}:{model}:{tag}"
        self._load()[key] = result
        self._save()

    def stats(self) -> dict:
        data = self._load()
        return {"total_cached": len(data), "cache_file": str(self.cache_file)}


class MultimodalAnalyzer:
    """多模态内容分析 - OpenAI兼容统一封装"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "Doubao-Seed-2.0-lite"
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=300.0
        )

        # 帧缓存
        self.cache = None
        try:
            from config import Config
            self.cache = FrameCache(Config.CACHE_DIR)
        except Exception:
            pass

        print(f"[MultimodalAnalyzer] 初始化完成，模型: {self.model}, 端点: {self.base_url}")

    def analyze_frame(self, image_path: str, use_cache: bool = True) -> Dict:
        """
        分析单帧图片（多模态）

        Args:
            image_path: 图片路径
            use_cache: 是否使用缓存（默认True）

        Returns:
            分析结果字典
        """
        # 缓存检查 (tag="scene" 区分于 speaker identification)
        if use_cache and self.cache:
            cached = self.cache.get(image_path, self.model, tag="scene")
            if cached:
                print(f"    [缓存命中] {Path(image_path).name}")
                return cached

        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = """Analyze this screenshot. Return ONLY JSON with these English keys:
{
    "scene_description": "brief scene description",
    "characters": [{"name": "name or unknown", "action": "what they are doing", "expression": "facial expression"}],
    "has_dialogue": true/false,
    "is_key_scene": true/false,
    "key_event": "key event description or null"
}

只输出JSON，不要其他内容。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            max_tokens=2048
        )

        content = response.choices[0].message.content
        # Extract first complete JSON object (brace-counting, avoids greedy match)
        json_start = content.find('{')
        result = None
        if json_start >= 0:
            brace_count = 0
            json_end = json_start
            for k in range(json_start, len(content)):
                if content[k] == '{':
                    brace_count += 1
                elif content[k] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = k + 1
                        break
            json_str = content[json_start:json_end]
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                result = None
        
        if result is not None and self.cache:
            self.cache.set(image_path, self.model, result)
        
        if result:
            return result
        else:
            return {"error": f"无法解析响应: {content}"}

    def analyze_frames_batch(
        self,
        frame_paths: List[str],
        delay: float = 0.5,
        retry_times: int = 3,
        checkpoint_path: str = None
    ) -> List[Dict]:
        """
        批量分析帧（带限流避免限流 + 增量保存）

        Args:
            frame_paths: 帧路径列表
            delay: 请求间隔（秒）
            retry_times: 失败重试次数
            checkpoint_path: 增量保存路径，每分析一帧就写入，中断不丢数据

        Returns:
            分析结果列表
        """
        import json as _json

        # 检查是否有断点可恢复
        results = []
        start_idx = 0
        if checkpoint_path:
            cp = Path(checkpoint_path)
            if cp.exists():
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        results = _json.load(f)
                    start_idx = len(results)
                    if start_idx > 0:
                        print(f"[断点恢复] 已有 {start_idx}/{len(frame_paths)} 帧，从第 {start_idx+1} 帧继续")
                except Exception:
                    pass

        for i in range(start_idx, len(frame_paths)):
            frame_path = frame_paths[i]
            print(f"分析帧 {i+1}/{len(frame_paths)}: {Path(frame_path).name}")

            for retry in range(retry_times):
                try:
                    result = self.analyze_frame(frame_path)
                    result["frame_path"] = frame_path
                    result["frame_index"] = i
                    results.append(result)

                    if "error" in result:
                        print(f"  警告: {result['error']}")

                    # 增量保存：每分析完一帧立即写入
                    if checkpoint_path:
                        cp_dir = Path(checkpoint_path).parent
                        cp_dir.mkdir(parents=True, exist_ok=True)
                        with open(checkpoint_path, "w", encoding="utf-8") as f:
                            _json.dump(results, f, ensure_ascii=False, indent=2)

                    break
                except Exception as e:
                    if retry < retry_times - 1:
                        print(f"  重试 {retry+1}/{retry_times}: {e}")
                        time.sleep(2)
                    else:
                        print(f"  帧分析失败: {e}")
                        results.append({
                            "error": str(e),
                            "frame_path": frame_path,
                            "frame_index": i
                        })
                        # 失败帧也要保存
                        if checkpoint_path:
                            with open(checkpoint_path, "w", encoding="utf-8") as f:
                                _json.dump(results, f, ensure_ascii=False, indent=2)

            if i < len(frame_paths) - 1:
                time.sleep(delay)

        return results

    def analyze_frames_batch_concurrent(
        self,
        frame_paths: List[str],
        max_workers: int = 4,
        delay: float = 0.3
    ) -> List[Dict]:
        """
        并发分析帧（多线程）

        Args:
            frame_paths: 帧路径列表
            max_workers: 最大并发数
            delay: 请求间隔（秒）

        Returns:
            分析结果列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(frame_paths)

        def analyze_with_index(args):
            idx, frame_path = args
            try:
                time.sleep(delay)
                result = self.analyze_frame(frame_path)
                result["frame_path"] = frame_path
                result["frame_index"] = idx
                return idx, result
            except Exception as e:
                return idx, {
                    "error": str(e),
                    "frame_path": frame_path,
                    "frame_index": idx
                }

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_with_index, (i, fp)): i
                for i, fp in enumerate(frame_paths)
            }

            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                print(f"完成帧 {idx+1}/{len(frame_paths)}")

        return results


    def identify_speaker(self, image_path: str, context_characters: list = None) -> Dict:
        """识别画面中正在说话的人物
        
        Args:
            image_path: 帧路径
            context_characters: 本集已识别的人物列表 [{"name":"张三", "description":"..."}]
        
        Returns:
            {"speaker_name": "张三", "confidence": 0.9, "description": "..."}
        """
        # 缓存检查 (tag="speaker" 区分于 scene analysis)
        if self.cache:
            cached = self.cache.get(image_path, self.model, tag="speaker")
            if cached:
                return cached

        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        char_hint = ""
        if context_characters:
            names = [c.get("name", "") for c in context_characters if c.get("name")]
            if names:
                char_hint = f"\n本集已出现的人物: {', '.join(names)}"

        prompt = f"""分析这张截图，只回答一个问题：画面中谁在说话？

判断依据：嘴型、面部朝向、手势、其他人的视线方向。
如果画面中有多个人，只输出正在说话的那个人。
如果无法确定，输出 "unknown"。
{char_hint}

请用JSON格式输出，只输出JSON:{{"speaker_name":"人物名或unknown","confidence":0.0-1.0,"evidence":"简短依据"}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=256
        )

        content = response.choices[0].message.content

        # Extract JSON
        import json
        json_start = content.find('{')
        if json_start >= 0:
            brace_count = 0
            json_end = json_start
            for k in range(json_start, len(content)):
                if content[k] == '{':
                    brace_count += 1
                elif content[k] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = k + 1
                        break
            try:
                result = json.loads(content[json_start:json_end])
                if self.cache:
                    self.cache.set(image_path, self.model, result, tag="speaker")
                return result
            except json.JSONDecodeError:
                pass
        return {"speaker_name": "unknown", "confidence": 0.0, "evidence": "parse failed"}


    def analyze_expression(self, image_path: str) -> Dict:
        """分析画面中人物的表情感染力 (0-5)

        Returns:
            {"intensity": 3, "emotion": "震惊", "evidence": "双眼圆睁嘴巴大张"}
        """
        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = """分析这张截图中人物的表情感染力，打分0-5。

0-面无表情: 人物面部平静，无明显情绪。例: "男子面无表情直视前方"
1-微表情: 轻微情绪流露，嘴角微动或眉头轻皱。例: "女子轻皱眉头，若有所思"
2-明显情绪: 清晰的情绪表达，微笑/皱眉/瞪眼。例: "男子露出微笑，眼神温和"
3-强烈情绪: 夸张的面部表情，大笑/愤怒/悲伤。例: "女子怒目圆睁，咬牙切齿"
4-极端情绪: 面部扭曲，大哭/暴怒/极度恐惧。例: "男子面目狰狞，青筋暴起"
5-失控: 崩溃大哭、歇斯底里、面部完全失控。例: "女子瘫坐地上掩面嚎啕，面部扭曲"

返回JSON: {"intensity":0-5,"emotion":"情绪类型","evidence":"引用画面关键特征"}
只输出JSON。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=256
        )

        content = response.choices[0].message.content
        import json as _json
        start = content.find('{')
        if start >= 0:
            brace_count = 0
            for k in range(start, len(content)):
                if content[k] == '{': brace_count += 1
                elif content[k] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return _json.loads(content[start:k+1])
                        except _json.JSONDecodeError:
                            pass
                        break
        return {"intensity": 0, "emotion": "unknown", "evidence": "parse failed"}
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            test_image = Path(__file__).parent / "test_frame.jpg"
            if test_image.exists():
                self.analyze_frame(str(test_image))
                print("API连接测试成功")
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Hello, this is a test."}],
                    max_tokens=32
                )
                if response and response.choices:
                    print("API连接测试成功")
                else:
                    print("API连接测试失败: 无响应")
                    return False
            return True
        except Exception as e:
            print(f"API连接测试失败: {e}")
            return False
