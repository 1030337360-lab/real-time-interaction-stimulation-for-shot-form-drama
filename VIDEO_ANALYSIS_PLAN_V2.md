# 短剧视频AI理解与剧情图谱构建方案（简化版）

> 本文档针对**单机LAN短剧项目**优化，聚焦快速验证和轻量部署。

---

## 一、项目目标

### 1.1 核心目标
- 通过AI多模态大模型理解视频内容，自动生成高光点和剧情摘要
- 构建人物关系图谱，支持跨剧集的人物追踪
- **直接替代手动高光点标记**，降低运营成本

### 1.2 与现有高光系统的关系

```
现有系统:                    新系统增强:
highlights: number[]  ──►  自动从 ai_analysis 生成 highlights[]
手动标记高光点              AI分析 + 可选人工修正
单集独立高光               跨集人物关系追踪
```

**关键结论**: `ai_analysis` 中的关键场景（`key_scenes`）可自动映射为高光点，优先级: `critical > high > medium`

---

## 二、技术选型（最终决定）

### 2.1 选型原则
- **单机部署优先**: 不引入分布式组件
- **快速验证优先**: 选最容易跑通的方案
- **成本可控**: 明码标价，避免上线后账单爆炸

### 2.2 最终选型

| 组件 | 选择 | 原因 |
|------|------|------|
| 图数据库 | **NetworkX + JSON** | 轻量、无需独立部署、够用 |
| 多模态模型 | **Qwen-VL2.5** | 中文好、API稳定、价格低 |
| 任务队列 | **直接调用** | 单机不需要，先跑通再说 |
| 部署方式 | **python main.py** | 不需要Docker，先验证 |

> ⚠️ **Neo4j 放弃理由**: 部署复杂、资源占用高。NetworkX 完全满足单项目人物关系存储需求，未来如需扩展可平滑迁移。

---

## 三、成本估算

### 3.1 输入规模
```
假设: 22集 × 5分钟 × 1fps = 6600帧/剧
```

### 3.2 Qwen-VL2.5 API费用

```
基础费用（截至2025年5月）:
- 输入图片: ¥0.012/张
- 视频理解: ¥0.08/分钟

单剧成本:
- 6600帧 ÷ 60帧/分钟 × ¥0.08 = ¥8.8/集
- 或直接用图片API: 6600张 × ¥0.012 = ¥79.2/集 ⚠️太贵！

推荐策略: 每集采样30-50张关键帧
- 30张 × ¥0.012 = ¥0.36/集
- 22集 × ¥0.36 = ¥7.92/剧
```

### 3.3 优化策略

1. **关键帧采样**: 优先选择场景切换帧、有文字帧
2. **批量调用**: 合并多帧为单次请求
3. **缓存结果**: 避免重复分析同一剧集
4. **增量解析**: 只解析新增剧集

### 3.4 存储估算

```
单集存储需求:
- 30张关键帧（JPEG压缩）: 30 × 100KB = 3MB
- JSON metadata: ~50KB
- 人物关系图: ~10KB
总计: ~3.06MB/集

22集 × 3MB = 66MB（合理）

⚠️ 注意: drama.json 只存metadata，图片存独立目录
```

---

## 四、真实Walkthrough示例

### 4.1 示例剧集
**剧名**: 天下第一纨绔  
**集数**: 第1集  
**时长**: 5分钟  
**分析帧数**: 30张关键帧

### 4.2 AI分析过程

#### Step 1: 抽帧命令
```bash
# 使用FFmpeg提取关键帧（每秒1帧，取前5分钟）
ffmpeg -i "天下第一纨绔/第1集.mp4" -vf "select='between(t,0,300)',fps=1" -q:v 2 frames/episode_1/frame_%03d.jpg

# 场景切换检测（更智能的采样）
ffmpeg -i "天下第一纨绔/第1集.mp4" -vf "select='gt(scene,0.3)',fps=fps=1/5" -q:v 2 frames/episode_1/scene_%03d.jpg
```

#### Step 2: 逐帧调用Qwen-VL
```python
# 示例: 单帧分析Prompt
prompt = """
分析这张截图，提取以下信息（JSON格式）:
{
    "scene_description": "场景描述",
    "characters": [{"name": "姓名", "action": "在做什么", "emotion": "表情/情绪"}],
    "has_dialogue": true/false,
    "is_key_scene": true/false,  # 是否有重要事件
    "key_event": "关键事件描述（若无则null）"
}
"""

response = qwen_vl.analyze(image_path, prompt)
```

#### Step 3: 30帧分析结果汇总
```json
{
  "frame_001": {
    "scene_description": "古风府邸庭院，阳光明媚",
    "characters": [
      {"name": "张云起", "action": "躺在躺椅上嗮太阳", "emotion": "慵懒"}
    ],
    "has_dialogue": false,
    "is_key_scene": false,
    "key_event": null
  },
  "frame_015": {
    "scene_description": "大厅内，家族长辈训话",
    "characters": [
      {"name": "张云起", "action": "被训斥", "emotion": "无奈"},
      {"name": "张老爷", "action": "严厉训斥", "emotion": "愤怒"}
    ],
    "has_dialogue": true,
    "is_key_scene": true,
    "key_event": "张云起被父亲当众羞辱，立下三个月内证明自己的誓言"
  },
  "frame_028": {
    "scene_description": "街头酒楼外",
    "characters": [
      {"name": "张云起", "action": "与陌生人争执", "emotion": "挑衅"},
      {"name": "李天骄", "action": "出手干预", "emotion": "轻蔑"}
    ],
    "has_dialogue": true,
    "is_key_scene": true,
    "key_event": "张云起结识李天骄（城守之子），两人针锋相对"
  }
}
```

### 4.3 LLM二次提取（结构化）

```python
# 将30帧描述合并，用LLM提取结构化信息
summary_prompt = """
根据以下剧集帧分析，提取人物和关系:

【帧分析】
[frame_015] 张云起被父亲张老爷当众训斥，立下誓言
[frame_028] 张云起与李天骄街头相遇，针锋相对
[frame_045] 张云起遇到神秘女子（赵青竹），她出手相助
...

请以JSON格式输出:
{
  "summary": "本集摘要（100字内）",
  "characters": [
    {
      "id": "char_001",
      "name": "张云起",
      "role": "protagonist",
      "first_appearance": "frame_001",
      "description": "纨绔子弟，实则深藏不露"
    },
    {
      "id": "char_002", 
      "name": "张老爷",
      "role": "supporting",
      "first_appearance": "frame_015",
      "description": "张云起之父，严厉但关心儿子"
    },
    {
      "id": "char_003",
      "name": "李天骄",
      "role": "antagonist",
      "first_appearance": "frame_028",
      "description": "城守之子，与张云起为竞争对手"
    }
  ],
  "relationships": [
    {
      "source": "char_001",
      "target": "char_002", 
      "type": "父子",
      "strength": 0.8,
      "evidence": "frame_015, frame_056"
    },
    {
      "source": "char_001",
      "target": "char_003",
      "type": "对手",
      "strength": 0.9,
      "evidence": "frame_028, frame_089"
    }
  ],
  "key_scenes": [
    {
      "frame": "frame_015",
      "timestamp": 75,
      "title": "立下誓言",
      "importance": "high",
      "emotional_impact": 8
    },
    {
      "frame": "frame_028",
      "timestamp": 140,
      "title": "双雄初遇",
      "importance": "critical",
      "emotional_impact": 9
    }
  ]
}
"""

structured_result = llm.extract(summary_prompt)
```

### 4.4 最终输出

```json
{
  "episode_id": 1,
  "ai_analysis": {
    "summary": "张云起是江州城有名的纨绔子弟，整日无所事事。这一日被父亲当众训斥后，他立下三月之约，要在科举中证明自己。街头偶遇城守之子李天骄，两人针锋相对，张云起险些吃亏，幸得神秘女子赵青竹出手相助。",
    "characters": [
      {
        "id": "char_001",
        "name": "张云起",
        "role": "protagonist",
        "first_appearance": 0,
        "description": "外表纨绔内心有志的世家子弟",
        "episode_appearances": [1, 2, 3]
      },
      {
        "id": "char_002",
        "name": "张老爷", 
        "role": "supporting",
        "first_appearance": 75,
        "description": "严父形象，对儿子恨铁不成钢",
        "episode_appearances": [1]
      },
      {
        "id": "char_003",
        "name": "李天骄",
        "role": "antagonist", 
        "first_appearance": 140,
        "description": "城守之子，文武双全的学霸",
        "episode_appearances": [1, 2, 4]
      },
      {
        "id": "char_004",
        "name": "赵青竹",
        "role": "supporting",
        "first_appearance": 180,
        "description": "神秘女子，武功高强",
        "episode_appearances": [1, 5, 8]
      }
    ],
    "relationships": [
      {
        "source_id": "char_001",
        "target_id": "char_002",
        "type": "父子",
        "strength": 0.9,
        "description": "表面叛逆，实则渴望父亲认可",
        "episodes": [1]
      },
      {
        "source_id": "char_001",
        "target_id": "char_003",
        "type": "对手",
        "strength": 0.85,
        "description": "科举路上的最大竞争者",
        "episodes": [1, 2, 4]
      },
      {
        "source_id": "char_001",
        "target_id": "char_004",
        "type": "恩人/暧昧",
        "strength": 0.6,
        "description": "初次相助，缘分开始",
        "episodes": [1]
      }
    ],
    "key_scenes": [
      {
        "frame": "frame_015",
        "timestamp": 75,
        "title": "立下誓言",
        "description": "张云起被父亲当众羞辱，立下三月之约",
        "importance": "high",
        "emotional_impact": 8,
        "tags": ["冲突", "励志", "转折"]
      },
      {
        "frame": "frame_028",
        "timestamp": 140,
        "title": "双雄初遇",
        "description": "张云起与李天骄街头相遇，针锋相对",
        "importance": "critical",
        "emotional_impact": 9,
        "tags": ["冲突", "对手戏", "高能"]
      }
    ],
    "highlights_auto": [75, 140],  // ⭐ 自动生成的高光点（供现有系统使用）
    "confidence_score": 0.82,
    "analyzed_at": "2026-05-22T10:30:00Z",
    "frames_used": 30,
    "cost_estimate": 0.36
  }
}
```

### 4.5 人物关系图谱（NetworkX格式）

```python
import networkx as nx

# 创建人物关系图
G = nx.Graph()

# 添加节点
G.add_node("char_001", name="张云起", role="protagonist")
G.add_node("char_002", name="张老爷", role="supporting")
G.add_node("char_003", name="李天骄", role="antagonist")
G.add_node("char_004", name="赵青竹", role="supporting")

# 添加边（关系）
G.add_edge("char_001", "char_002", relation="父子", strength=0.9)
G.add_edge("char_001", "char_003", relation="对手", strength=0.85)
G.add_edge("char_001", "char_004", relation="恩人/暧昧", strength=0.6)

# 导出为JSON
graph_data = nx.node_link_data(G)
print(json.dumps(graph_data, ensure_ascii=False, indent=2))
```

```json
{
  "directed": false,
  "graph": {"drama_id": 1, "title": "天下第一纨绔"},
  "nodes": [
    {"id": "char_001", "name": "张云起", "role": "protagonist"},
    {"id": "char_002", "name": "张老爷", "role": "supporting"},
    {"id": "char_003", "name": "李天骄", "role": "antagonist"},
    {"id": "char_004", "name": "赵青竹", "role": "supporting"}
  ],
  "links": [
    {"source": "char_001", "target": "char_002", "relation": "父子", "strength": 0.9},
    {"source": "char_001", "target": "char_003", "relation": "对手", "strength": 0.85},
    {"source": "char_001", "target": "char_004", "relation": "恩人/暧昧", "strength": 0.6}
  ]
}
```

---

## 五、系统架构（简化版）

### 5.1 整体架构

```
┌────────────────────────────────────────────────────┐
│                 短剧播放闭环系统                     │
├────────────────────────────────────────────────────┤
│                                                     │
│   ┌──────────┐      ┌──────────┐                  │
│   │  React   │◄────►│ Express  │                  │
│   │  (前端)   │      │  (API)   │                  │
│   └──────────┘      └──────────┘                  │
│         │                  │                       │
│         │          ┌───────┴───────┐               │
│         │          ▼               ▼               │
│         │    ┌─────────┐    ┌─────────┐          │
│         │    │  Redis  │    │  lowdb  │          │
│         │    └─────────┘    └─────────┘          │
│         │                  │                       │
│         │          ┌───────┴───────┐               │
│         │          ▼               ▼               │
│         │    ┌─────────┐    ┌─────────────────┐   │
│         │    │ Drama   │    │ Character Graph │   │
│         │    │ .json   │    │  _global.json   │   │
│         │    └─────────┘    └─────────────────┘   │
│         │                                             │
└─────────┴─────────────────────────────────────────────┘

        独立Python解析服务（可选，常驻或按需启动）
        │
        ├─ ffmpeg 抽帧
        ├─ Qwen-VL API 调用
        ├─ LLM 结构化提取
        └─ 结果写入 lowdb + JSON文件
```

### 5.2 数据文件结构

```
server/
├── database/
│   ├── drama.json              # 剧集元数据 + ai_analysis
│   └── character_graph_global.json  # ⭐ 跨剧集人物关系（独立文件）
│
├── analysis/                   # ⭐ 新增: AI分析相关
│   ├── frames/                 # 关键帧图片（定期清理）
│   │   └── episode_1/
│   │       ├── frame_001.jpg
│   │       └── ...
│   └── cache/                  # 分析缓存
│       └── episode_1_analysis.json
│
└── app.js                     # Express主入口（不变）
```

---

## 六、核心Python模块（完整实现）

### 6.1 项目结构

```
python/
├── main.py                    # 入口脚本
├── config.py                  # 配置
├── video_preprocessor.py      # 视频预处理（FFmpeg）
├── multimodal_analyzer.py      # 多模态分析（Qwen-VL）
├── structured_extractor.py     # 结构化提取（LLM）
├── graph_builder.py           # 图谱构建（NetworkX）
├── storage.py                 # 结果存储
└── requirements.txt           # 依赖
```

### 6.2 配置文件

```python
# config.py
import os

class Config:
    # 视频目录
    VIDEO_DIR = r"D:\video_data\videos"
    
    # 输出目录
    OUTPUT_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database"
    
    # 帧存储目录（临时）
    FRAME_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis\frames"
    
    # Qwen-VL API配置
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_MODEL = "qwen-vl-plus"  # 或 qwen-vl-max
    
    # 采样配置
    FRAMES_PER_EPISODE = 30  # 每集采样30帧
    FRAME_RATE = 1  # 每秒1帧
    
    # 缓存配置
    USE_CACHE = True  # 跳过已分析的剧集
    
    # lowdb配置（复用现有的）
    LOWDB_PATH = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database\drama.json"
    
    # 人物关系图谱文件
    GRAPH_FILE = os.path.join(OUTPUT_DIR, "character_graph_global.json")
```

### 6.3 视频预处理

```python
# video_preprocessor.py
import os
import subprocess
from pathlib import Path

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
    ) -> list[str]:
        """
        提取关键帧
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            num_frames: 要提取的帧数
        
        Returns:
            帧文件路径列表
        """
        video_path = Path(video_path)
        episode_name = video_path.stem  # e.g., "第1集"
        episode_dir = Path(output_dir) / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取视频时长（秒）
        duration = self._get_duration(video_path)
        
        # 计算采样间隔
        interval = max(1, int(duration / num_frames))
        
        # FFmpeg命令: 每interval秒抽一帧
        output_pattern = str(episode_dir / "frame_%03d.jpg")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval}",  # 每interval秒1帧
            "-q:v", "2",  # JPEG质量
            "-frames:v", str(num_frames),  # 最多num_frames帧
            output_pattern,
            "-y"  # 覆盖已存在文件
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg错误: {result.stderr}")
            raise RuntimeError(f"抽帧失败: {result.stderr}")
        
        # 获取生成的文件列表
        frames = sorted(episode_dir.glob("frame_*.jpg"))
        print(f"提取了 {len(frames)} 帧到 {episode_dir}")
        
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
        return float(result.stdout.strip())
    
    def extract_audio(self, video_path: str, output_path: str) -> str:
        """提取音频（用于ASR，可选）"""
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # 不要视频
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_path,
            "-y"
        ]
        subprocess.run(cmd, capture_output=True)
        return output_path
```

### 6.4 多模态分析

```python
# multimodal_analyzer.py
import base64
import requests
import time
from pathlib import Path

class MultimodalAnalyzer:
    """多模态内容分析 - Qwen-VL封装"""
    
    def __init__(self, api_key: str, model: str = "qwen-vl-plus"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    
    def analyze_frame(self, image_path: str) -> dict:
        """
        分析单帧图片
        
        Args:
            image_path: 图片路径
        
        Returns:
            分析结果字典
        """
        # 读取图片并转为base64
        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        # 构建请求
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
        
        # 调用API
        response = requests.post(self.api_url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"API调用失败: {response.text}")
        
        result = response.json()
        
        # 解析返回内容
        try:
            content = result["output"]["choices"][0]["message"]["content"]
            # 提取JSON部分
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": f"无法解析响应: {content}"}
        except (KeyError, IndexError) as e:
            return {"error": f"解析错误: {str(e)}, 原始响应: {result}"}
    
    def analyze_frames_batch(self, frame_paths: list[str], delay: float = 0.5) -> list[dict]:
        """
        批量分析帧（带延迟避免限流）
        
        Args:
            frame_paths: 帧路径列表
            delay: 请求间隔（秒）
        
        Returns:
            分析结果列表
        """
        results = []
        
        for i, frame_path in enumerate(frame_paths):
            print(f"分析帧 {i+1}/{len(frame_paths)}: {Path(frame_path).name}")
            
            try:
                result = self.analyze_frame(frame_path)
                result["frame_path"] = frame_path
                result["frame_index"] = i
                results.append(result)
            except Exception as e:
                print(f"帧分析失败: {e}")
                results.append({"error": str(e), "frame_path": frame_path, "frame_index": i})
            
            # 避免API限流
            if i < len(frame_paths) - 1:
                time.sleep(delay)
        
        return results
```

### 6.5 结构化提取

```python
# structured_extractor.py
import json
import requests
import time
from typing import Optional

class StructuredExtractor:
    """结构化信息提取 - 基于LLM"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def extract_summary(self, frame_analyses: list[dict], episode_title: str = "") -> dict:
        """
        从帧分析结果中提取结构化信息
        
        Args:
            frame_analyses: 帧分析结果列表
            episode_title: 剧集标题
        
        Returns:
            结构化提取结果
        """
        # 过滤有效结果
        valid_analyses = [a for a in frame_analyses if "error" not in a]
        
        # 构建汇总Prompt
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
  "highlights_auto": [75, 140, 200]  // 自动生成的高光点时间戳
}}

只输出JSON，不要其他内容。"""
        
        # 调用LLM（使用通义千问或其他LLM API）
        result = self._call_llm(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": f"无法解析LLM响应: {result}"}
        except Exception as e:
            return {"error": f"解析错误: {e}"}
    
    def _call_llm(self, prompt: str, model: str = "qwen-plus") -> str:
        """调用LLM API"""
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
        payload = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"max_tokens": 2000}
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"LLM API调用失败: {response.text}")
        
        result = response.json()
        return result["output"]["choices"][0]["message"]["content"]
    
    def map_to_highlights(
        self, 
        key_scenes: list[dict], 
        video_duration: float
    ) -> list[int]:
        """
        将关键场景映射为高光点
        
        Args:
            key_scenes: 关键场景列表
            video_duration: 视频总时长（秒）
        
        Returns:
            高光点时间戳列表（秒）
        """
        highlights = []
        
        for scene in key_scenes:
            # 只选取 importance 为 high 或 critical 的场景
            if scene.get("importance") in ["high", "critical"]:
                # 优先使用 timestamp，否则从 frame_index 估算
                timestamp = scene.get("timestamp")
                if timestamp is None:
                    frame_index = scene.get("frame_index", 0)
                    # 假设30帧均匀分布
                    timestamp = int((frame_index / 30) * video_duration)
                
                highlights.append(int(timestamp))
        
        return sorted(set(highlights))  # 去重并排序
```

### 6.6 图谱构建

```python
# graph_builder.py
import json
import networkx as nx
from pathlib import Path
from typing import Optional

class GraphBuilder:
    """人物关系图谱构建 - NetworkX"""
    
    def __init__(self, graph_file: str):
        self.graph_file = Path(graph_file)
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)
    
    def build_episode_graph(
        self, 
        analysis_result: dict,
        episode_id: int
    ) -> nx.Graph:
        """
        为单个剧集构建人物关系图
        
        Args:
            analysis_result: 结构化分析结果
            episode_id: 剧集ID
        
        Returns:
            NetworkX图对象
        """
        G = nx.Graph()
        G.graph["episode_id"] = episode_id
        
        # 添加人物节点
        for char in analysis_result.get("characters", []):
            G.add_node(
                char["id"],
                name=char["name"],
                role=char["role"],
                description=char.get("description", ""),
                first_appearance=char.get("first_appearance", 0)
            )
        
        # 添加关系边
        for rel in analysis_result.get("relationships", []):
            G.add_edge(
                rel["source_id"],
                rel["target_id"],
                relation=rel["type"],
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
        """
        将剧集图谱合并到全局图谱
        
        Args:
            episode_graph: 单集图谱
            drama_id: 剧ID
        
        Returns:
            更新后的全局图谱
        """
        # 加载或创建全局图谱
        global_graph = self.load_global_graph(drama_id)
        
        # 合并节点
        for node, attrs in episode_graph.nodes(data=True):
            if node in global_graph.nodes:
                # 更新已有节点属性
                for key, value in attrs.items():
                    if key not in global_graph.nodes[node]:
                        global_graph.nodes[node][key] = value
                # 更新出现集数
                if "episodes" not in global_graph.nodes[node]:
                    global_graph.nodes[node]["episodes"] = []
                if episode_graph.graph["episode_id"] not in global_graph.nodes[node]["episodes"]:
                    global_graph.nodes[node]["episodes"].append(episode_graph.graph["episode_id"])
            else:
                # 新增节点
                global_graph.add_node(node, **attrs, episodes=[episode_graph.graph["episode_id"]])
        
        # 合并边
        for u, v, attrs in episode_graph.edges(data=True):
            if global_graph.has_edge(u, v):
                # 更新已有边
                existing_episodes = global_graph.edges[u, v].get("episodes", [])
                if episode_graph.graph["episode_id"] not in existing_episodes:
                    existing_episodes.append(episode_graph.graph["episode_id"])
                    global_graph.edges[u, v]["episodes"] = existing_episodes
                # 更新关系强度（取最大值）
                if attrs.get("strength", 0) > global_graph.edges[u, v].get("strength", 0):
                    global_graph.edges[u, v]["strength"] = attrs["strength"]
            else:
                # 新增边
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
    
    def get_character_network(
        self, 
        character_id: str, 
        depth: int = 2
    ) -> dict:
        """
        获取指定人物的社交网络
        
        Args:
            character_id: 人物ID
            depth: 关系深度
        
        Returns:
            网络数据字典
        """
        graph = self.load_global_graph(None)
        
        if character_id not in graph:
            return {"error": f"人物 {character_id} 不存在"}
        
        # 获取指定深度的子图
        neighbors = nx.single_source_shortest_path_length(graph, character_id, cutoff=depth)
        subgraph = graph.subgraph(neighbors.keys())
        
        return nx.node_link_data(subgraph)
```

### 6.7 结果存储

```python
# storage.py
import json
from pathlib import Path
from typing import Optional

class AnalysisStorage:
    """分析结果存储 - 直接读写JSON文件"""
    
    def __init__(self, json_path: str):
        self.path = Path(json_path)
    
    def _load_data(self) -> dict:
        """加载JSON数据"""
        if not self.path.exists():
            return {"episodes": []}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_data(self, data: dict):
        """保存JSON数据"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def update_episode_analysis(
        self,
        episode_id: int,
        analysis_result: dict
    ):
        """
        更新剧集的AI分析结果
        
        Args:
            episode_id: 剧集ID
            analysis_result: 分析结果
        """
        data = self._load_data()
        
        for ep in data.get("episodes", []):
            if ep.get("id") == episode_id:
                ep["ai_analysis"] = analysis_result
                break
        
        self._save_data(data)
    
    def get_episode_analysis(self, episode_id: int) -> Optional[dict]:
        """获取剧集分析结果"""
        data = self._load_data()
        
        for ep in data.get("episodes", []):
            if ep.get("id") == episode_id:
                return ep.get("ai_analysis")
        
        return None
    
    def batch_update_episodes(
        self,
        updates: list[tuple[int, dict]]
    ):
        """
        批量更新剧集分析结果
        
        Args:
            updates: [(episode_id, analysis_result), ...]
        """
        data = self._load_data()
        episode_ids = {ep["id"]: ep for ep in data.get("episodes", [])}
        
        for episode_id, analysis_result in updates:
            if episode_id in episode_ids:
                episode_ids[episode_id]["ai_analysis"] = analysis_result
        
        self._save_data(data)
    
    def get_all_episodes(self) -> list:
        """获取所有剧集"""
        data = self._load_data()
        return data.get("episodes", [])
    
    def get_episode_by_id(self, episode_id: int) -> Optional[dict]:
        """根据ID获取剧集"""
        data = self._load_data()
        for ep in data.get("episodes", []):
            if ep.get("id") == episode_id:
                return ep
        return None
```

### 6.8 主入口脚本

```python
# main.py
#!/usr/bin/env python3
"""
短剧AI分析主脚本
用法:
    python main.py                          # 分析所有剧集
    python main.py --episode 1            # 分析指定剧集
    python main.py --drama "天下第一纨绔"  # 分析指定剧的所有集
    python main.py --force                # 强制重新分析（忽略缓存）
"""

import argparse
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from video_preprocessor import VideoPreprocessor
from multimodal_analyzer import MultimodalAnalyzer
from structured_extractor import StructuredExtractor
from graph_builder import GraphBuilder
from storage import AnalysisStorage


def analyze_episode(
    episode_id: int,
    video_path: str,
    analyzer: MultimodalAnalyzer,
    extractor: StructuredExtractor,
    graph_builder: GraphBuilder,
    storage: AnalysisStorage,
    force: bool = False
) -> dict:
    """分析单个剧集"""
    print(f"\n{'='*60}")
    print(f"开始分析剧集 #{episode_id}: {Path(video_path).name}")
    print(f"{'='*60}")
    
    # 1. 检查缓存
    if not force:
        cached = storage.get_episode_analysis(episode_id)
        if cached:
            print(f"✓ 已存在分析结果，跳过（使用 --force 强制重新分析）")
            return cached
    
    # 2. 视频预处理 - 提取关键帧
    preprocessor = VideoPreprocessor(Config.FRAME_DIR)
    frames = preprocessor.extract_key_frames(
        video_path,
        str(Path(Config.FRAME_DIR) / f"episode_{episode_id}"),
        num_frames=Config.FRAMES_PER_EPISODE
    )
    
    if not frames:
        raise RuntimeError("抽帧失败，未获取到任何帧")
    
    # 3. 多模态分析 - 逐帧分析
    print(f"\n开始调用Qwen-VL分析 {len(frames)} 帧...")
    frame_analyses = analyzer.analyze_frames_batch(frames, delay=0.5)
    
    # 4. 结构化提取 - LLM总结
    print(f"\n开始LLM结构化提取...")
    structured = extractor.extract_summary(
        frame_analyses,
        episode_title=Path(video_path).parent.name
    )
    
    # 5. 映射高光点
    video_duration = preprocessor._get_duration(video_path)
    highlights = extractor.map_to_highlights(
        structured.get("key_scenes", []),
        video_duration
    )
    structured["highlights_auto"] = highlights
    
    # 6. 添加元信息
    structured["episode_id"] = episode_id
    structured["confidence_score"] = 0.8  # TODO: 实际计算
    structured["frames_used"] = len(frames)
    structured["cost_estimate"] = len(frames) * 0.012  # 估算费用
    structured["analyzed_at"] = "2026-05-22T10:30:00Z"  # TODO: 实际时间
    
    # 7. 构建图谱
    episode_graph = graph_builder.build_episode_graph(structured, episode_id)
    global_graph = graph_builder.merge_global_graph(episode_graph, drama_id=1)  # TODO: 获取实际drama_id
    graph_builder.save_global_graph(global_graph)
    
    # 8. 存储结果
    storage.update_episode_analysis(episode_id, structured)
    
    print(f"\n✓ 分析完成!")
    print(f"  - 识别人物: {len(structured.get('characters', []))}")
    print(f"  - 关系数量: {len(structured.get('relationships', []))}")
    print(f"  - 关键场景: {len(structured.get('key_scenes', []))}")
    print(f"  - 自动高光点: {highlights}")
    print(f"  - 估算费用: ¥{structured['cost_estimate']:.2f}")
    
    return structured


def main():
    parser = argparse.ArgumentParser(description="短剧AI分析工具")
    parser.add_argument("--episode", type=int, help="分析指定剧集ID")
    parser.add_argument("--drama", type=str, help="分析指定剧名的所有集")
    parser.add_argument("--force", action="store_true", help="强制重新分析")
    parser.add_argument("--all", action="store_true", help="分析所有剧集")
    args = parser.parse_args()
    
    # 初始化组件
    analyzer = MultimodalAnalyzer(Config.QWEN_API_KEY, Config.QWEN_MODEL)
    extractor = StructuredExtractor(Config.QWEN_API_KEY)
    graph_builder = GraphBuilder(Config.GRAPH_FILE)
    storage = AnalysisStorage(Config.LOWDB_PATH)
    
    # 根据参数执行
    if args.all:
        # 分析所有剧集
        episodes = storage.get_all_episodes()
        for episode in episodes:
            try:
                video_path = Path(Config.VIDEO_DIR) / episode.get("video_url", "")
                if video_path.exists():
                    analyze_episode(
                        episode["id"],
                        str(video_path),
                        analyzer, extractor, graph_builder, storage,
                        force=args.force
                    )
                else:
                    print(f"⚠ 视频文件不存在: {video_path}")
            except Exception as e:
                print(f"✗ 分析失败: {e}")
    
    elif args.episode:
        # 分析指定剧集
        episode_id = args.episode
        episode = storage.get_episode_by_id(episode_id)
        
        if not episode:
            print(f"✗ 剧集 #{episode_id} 不存在")
            return
        
        video_path = Path(Config.VIDEO_DIR) / episode.get("video_url", "")
        if not video_path.exists():
            print(f"✗ 视频文件不存在: {video_path}")
            return
        
        analyze_episode(
            episode_id,
            str(video_path),
            analyzer, extractor, graph_builder, storage,
            force=args.force
        )
    
    else:
        print("请指定要分析的剧集:")
        print("  --all              分析所有剧集")
        print("  --episode <id>     分析指定剧集")
        print("  --drama <name>     分析指定剧的所有集")


if __name__ == "__main__":
    main()
```

### 6.9 依赖文件

```text
# requirements.txt
requests>=2.28.0
networkx>=3.0
# 不需要 lowdb，直接用Python内置 json 模块
```

---

## 七、与前端集成

### 7.1 API扩展

```javascript
// server/app.js 新增路由
const fs = require('fs');
const path = require('path');

// 获取AI分析结果
app.get('/api/analysis/:episodeId', (req, res) => {
  const { episodeId } = req.params;
  const episode = db.data.episodes.find(e => e.id === parseInt(episodeId));

  if (!episode) {
    return res.status(404).json({ error: 'Episode not found' });
  }

  res.json(episode.ai_analysis || null);
});

// 获取人物关系图谱
app.get('/api/analysis/:episodeId/character-graph', (req, res) => {
  const graphPath = path.join(__dirname, '..', 'database', 'character_graph_global.json');

  if (fs.existsSync(graphPath)) {
    res.sendFile(graphPath);
  } else {
    res.json({ nodes: [], links: [], graph: {}, directed: false });
  }
});

// 获取全局人物关系（跨剧集）
app.get('/api/analysis/drama/:dramaId/global-graph', (req, res) => {
  const graphPath = path.join(__dirname, '..', 'database', 'character_graph_global.json');

  if (fs.existsSync(graphPath)) {
    res.sendFile(graphPath);
  } else {
    res.json({ nodes: [], links: [], graph: {}, directed: false });
  }
});

// 触发分析（可选）
app.post('/api/analysis/analyze', async (req, res) => {
  const { episodeId } = req.body;

  // TODO: 启动Python子进程执行分析
  // 或调用外部API

  res.json({ status: 'queued', episodeId });
});
```

### 7.2 React组件集成

```typescript
// 新增: 剧情摘要组件
const EpisodeSummary = ({ episodeId }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch(`/api/analysis/${episodeId}`)
      .then(res => res.json())
      .then(data => {
        setAnalysis(data);
        setLoading(false);
      });
  }, [episodeId]);
  
  if (loading) return <div>加载中...</div>;
  if (!analysis) return null;
  
  return (
    <div className="episode-summary">
      <h3>剧情摘要</h3>
      <p>{analysis.summary}</p>
      
      <h4>人物 ({analysis.characters?.length})</h4>
      <div className="character-list">
        {analysis.characters?.map(char => (
          <span key={char.id} className={`character-tag ${char.role}`}>
            {char.name}
          </span>
        ))}
      </div>
    </div>
  );
};

// VideoPlayer增强: 使用AI生成的高光点
const VideoPlayer = ({ episodeId, ...props }) => {
  const [highlights, setHighlights] = useState([]);
  
  useEffect(() => {
    fetch(`/api/analysis/${episodeId}`)
      .then(res => res.json())
      .then(data => {
        // 优先使用AI生成的高光点，否则使用手动标记
        if (data?.highlights_auto?.length > 0) {
          setHighlights(data.highlights_auto);
        }
      });
  }, [episodeId]);
  
  return (
    <VideoPlayerBase
      {...props}
      highlights={highlights}
    />
  );
};
```

---

## 八、实现步骤（精简版）

### Phase 1: 快速验证（2-3天）

**Day 1: 环境搭建**
- [ ] 安装FFmpeg
- [ ] 安装Python依赖
- [ ] 配置Qwen API Key
- [ ] 测试抽帧脚本

**Day 2: 单集分析**
- [ ] 实现完整分析流程
- [ ] 测试单集分析（天下第一纨绔第1集）
- [ ] 验证输出格式

**Day 3: 结果存储**
- [ ] 集成lowdb存储
- [ ] 实现结果读取API
- [ ] 前端展示剧情摘要

**产出**: 单集分析可运行，原型验证通过

### Phase 2: 完善功能（3-5天）

**功能清单**:
- [ ] 批量分析多集
- [ ] 人物关系图谱构建
- [ ] 高光点自动映射
- [ ] 跨剧集人物追踪

**产出**: 完整的人物关系系统

### Phase 3: 优化迭代（持续）

- [ ] 采样策略优化（智能选帧）
- [ ] Prompt工程优化
- [ ] 成本控制
- [ ] 人工校正界面

---

## 九、远期展望（可选）

以下功能暂不实现，标记为远期目标:

1. **实时解析**: 直播/短视频场景（与VOD技术路线完全不同）
2. **多模型切换**: 固定Qwen-VL先跑通
3. **分布式部署**: 单机足够再考虑
4. **用户反馈闭环**: 运营需求再说

---

## 十、文档变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-22 | v1.0 | 初始版本（简化版） |

---

**核心改进**:
✅ 添加完整Walkthrough示例（天下第一纨绔）  
✅ 明确选择NetworkX替代Neo4j  
✅ 明确AI生成高光点的关系  
✅ 删除过度设计（Docker/Prometheus/限流）  
✅ 添加成本估算和FFmpeg命令  
✅ 独立character_graph.json文件  
✅ 提供可运行的Python代码骨架  
