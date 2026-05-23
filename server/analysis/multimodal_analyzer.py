"""
多模态分析模块 - Qwen-VL封装
"""
import base64
import requests
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Optional


class MultimodalAnalyzer:
    """多模态内容分析 - Qwen-VL封装"""

    def __init__(self, api_key: str, model: str = "qwen-vl-plus"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    def analyze_frame(self, image_path: str) -> Dict:
        """
        分析单帧图片

        Args:
            image_path: 图片路径

        Returns:
            分析结果字典
        """
        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = """分析这张截图，提取以下信息:
1. 场景描述（简短）
2. 出现的人物（名字、动作、表情）
3. 是否有对话
4. 是否是关键场景（剧情转折、重要事件等）
5. 关键事件描述（若无则填null）

请用JSON格式输出，只输出JSON，不要其他内容。"""

        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": f"data:image/jpeg;base64,{img_base64}"},
                            {"text": prompt}
                        ]
                    }
                ]
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.api_url, json=payload, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"API调用失败: {response.text}")

        result = response.json()

        try:
            content = result["output"]["choices"][0]["message"]["content"]
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": f"无法解析响应: {content}"}
        except (KeyError, IndexError) as e:
            return {"error": f"解析错误: {str(e)}, 原始响应: {result}"}

    def analyze_frames_batch(
        self,
        frame_paths: List[str],
        delay: float = 0.5,
        retry_times: int = 3
    ) -> List[Dict]:
        """
        批量分析帧（带延迟避免限流）

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

    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            test_image = Path(__file__).parent / "test_frame.jpg"
            if test_image.exists():
                self.analyze_frame(str(test_image))
                print("API连接测试成功")
            else:
                prompt = "Hello, this is a test."
                payload = {
                    "model": self.model,
                    "input": {"prompt": prompt},
                    "parameters": {"result_format": "message"}
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                response = requests.post(self.api_url, json=payload, headers=headers)
                if response.status_code == 200:
                    print("API连接测试成功")
                else:
                    print(f"API连接测试失败: {response.status_code}")
                    return False
            return True
        except Exception as e:
            print(f"API连接测试失败: {e}")
            return False
