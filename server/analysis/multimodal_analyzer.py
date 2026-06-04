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

    @staticmethod
    def hash_frame(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def get(self, frame_path: str, model: str) -> dict | None:
        key = f"{self.hash_frame(frame_path)}:{model}"
        return self._load().get(key)

    def set(self, frame_path: str, model: str, result: dict):
        key = f"{self.hash_frame(frame_path)}:{model}"
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
        # 缓存检查
        if use_cache and self.cache:
            cached = self.cache.get(image_path, self.model)
            if cached:
                print(f"    [缓存命中] {Path(image_path).name}")
                return cached

        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = """分析这张截图，提取以下信息:
1. 场景描述（简短）
2. 出现的人物（名字、动作、表情）
3. 是否有对话
4. 是否是关键场景（剧情转折、重要事件等）
5. 关键事件描述（若无则填null）

请用JSON格式输出，只输出JSON，不要其他内容。"""

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
        else:
            result = None
        json_match = result

        if json_match is not None:
            if use_cache and self.cache:
                self.cache.set(image_path, self.model, json_match)
            return json_match
        return {"error": f"无法解析响应: {content}"}

    def analyze_frames_batch(
        self,
        frame_paths: List[str],
        delay: float = 0.5,
        retry_times: int = 3
    ) -> List[Dict]:
        """
        批量分析帧（带限流避免限流）

        Args:
            frame_paths: 帧路径列表
            delay: 请求间隔（秒）
            retry_times: 失败重试次数

        Returns:
            分析结果列表
        """
        results = []

        for i, frame_path in enumerate(frame_paths):
            print(f"分析帧 {i+1}/{len(frame_paths)}: {Path(frame_path).name}")

            for retry in range(retry_times):
                try:
                    result = self.analyze_frame(frame_path)
                    result["frame_path"] = frame_path
                    result["frame_index"] = i
                    results.append(result)

                    if "error" in result:
                        print(f"  警告: {result['error']}")

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
                return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
        return {"speaker_name": "unknown", "confidence": 0.0, "evidence": "parse failed"}

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
