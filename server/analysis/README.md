# 短剧视频AI分析服务

## 概述

本模块通过调用AI多模态大模型（Qwen-VL）对短剧视频进行理解和总结，自动提取人物、关系、关键场景，并构建人物关系图谱。

## 文件结构

```
server/analysis/
├── __init__.py              # Python包标识
├── config.py                # 配置文件（所有路径配置）
├── main.py                  # 主入口脚本
├── video_preprocessor.py    # 视频预处理（FFmpeg封装）
├── audio_analyzer.py         # 音频全流程分析（FunASR）
├── multimodal_analyzer.py   # 多模态分析（Qwen-VL API）
├── structured_extractor.py  # 结构化信息提取（LLM）
├── graph_builder.py         # 人物关系图谱构建（NetworkX）
├── storage.py               # 结果存储（独立JSON文件）
├── requirements.txt         # Python依赖
├── frames/                  # 抽帧临时目录
└── audio/                   # 音频临时目录
```

## 路径配置（config.py）

| 配置项 | 路径 | 说明 |
|--------|------|------|
| `VIDEO_DIR` | `D:\video_data\videos` | 原始视频文件目录 |
| `OUTPUT_DIR` | `server/database` | 输出目录 |
| `FRAME_DIR` | `server/analysis/frames` | 抽帧临时目录 |
| `LOWDB_PATH` | `server/database/drama.json` | Express服务的剧集数据库 |
| `ANALYSIS_RESULTS_PATH` | `server/database/analysis_results.json` | **AI分析结果存储** |
| `GRAPH_FILE` | `server/database/character_graph_global.json` | **人物关系图谱存储** |
| `CACHE_DIR` | `server/analysis/cache` | 缓存目录 |

## 数据流

```
视频文件 (D:\video_data\videos\)
        │
        ▼
┌─────────────────┐
│ video_preprocessor │  1. FFmpeg抽帧（30帧/集）
└─────────────────┘
        │
        ▼
┌─────────────────┐
│ multimodal_analyzer │  2. Qwen-VL逐帧分析
└─────────────────┘
        │
        ▼
┌─────────────────┐
│ structured_extractor │  3. LLM结构化提取
└─────────────────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌────────────────────┐  ┌───────────────┐
│ analysis_results.json │  │ character_graph_global.json │  │ highlights_auto │
│ (按video_url索引)    │  │ (NetworkX图谱)              │  │ (高光点时间戳) │
└───────────────┘  └────────────────────┘  └───────────────┘
```

## 存储文件格式

### analysis_results.json

```json
{
  "天下第一纨绔/第1集.mp4": {
    "ai_analysis": {
      "summary": "本集摘要...",
      "characters": [
        {
          "id": "char_001",
          "name": "主角名",
          "role": "protagonist",
          "description": "人物描述"
        }
      ],
      "relationships": [
        {
          "source_id": "char_001",
          "target_id": "char_002",
          "type": "敌对",
          "strength": 0.9
        }
      ],
      "key_scenes": [...],
      "highlights_auto": [45.5, 120.3, 185.0]
    },
    "updated_at": "2026-05-23T10:30:00Z"
  }
}
```

### character_graph_global.json

```json
{
  "directed": false,
  "graph": {"drama_id": 1},
  "nodes": [
    {
      "id": "char_001",
      "name": "主角名",
      "role": "protagonist",
      "episodes": [1, 2, 3]
    }
  ],
  "links": [
    {
      "source": "char_001",
      "target": "char_002",
      "relation": "敌对",
      "strength": 0.9,
      "episodes": [1, 2]
    }
  ]
}
```

## 使用方法

### 1. 安装依赖

```bash
cd server/analysis
pip install -r requirements.txt
```

### 2. 设置环境变量

```bash
# Windows
set QWEN_API_KEY=your_api_key

# Linux/Mac
export QWEN_API_KEY=your_api_key
```

### 3. 运行分析

```bash
# 查看统计
python main.py --stats

# 分析指定剧集（按ID）
python main.py --episode 1

# 分析指定剧集（按video_url）
python main.py --video-url "天下第一纨绔/第1集.mp4"

# 分析所有剧集
python main.py --all

# 强制重新分析（忽略缓存）
python main.py --all --force
```

## 模块说明

### video_preprocessor.py

- `extract_key_frames()`: 按固定间隔抽帧
- `extract_key_frames_smart()`: 基于场景切换检测抽帧
- `_get_duration()`: 使用ffprobe获取视频时长

### multimodal_analyzer.py

- `analyze_frame()`: 调用Qwen-VL分析单帧
- `analyze_frames_batch()`: 串行批量分析（带限流）
- `analyze_frames_batch_concurrent()`: 并发批量分析

### structured_extractor.py

- `extract_summary()`: 从帧分析结果提取结构化信息
- `map_to_highlights()`: 将关键场景映射为高光点时间戳

### graph_builder.py

- `build_episode_graph()`: 构建单集人物关系图
- `merge_global_graph()`: 合并到全局图谱
- `export_to_d3_json()`: 导出D3.js可用格式

### storage.py

- `update_episode_analysis()`: 按video_url存储分析结果
- `get_episode_analysis()`: 获取分析结果
- `get_statistics()`: 获取统计信息

## 与Express服务的关系

| 文件 | Express服务 | 分析服务 |
|------|------------|---------|
| `drama.json` | 写入方（scanVideoDirectory） | 只读（load_episodes） |
| `analysis_results.json` | 只读 | 写入方 |
| `character_graph_global.json` | 只读 | 写入方 |

---

## 音频分析模块（audio_analyzer.py）

### 环境要求

已配置好 Anaconda 虚拟环境 `glm-4`，CUDA 可用。

```bash
# 激活虚拟环境
conda activate glm-4

# 安装依赖
cd server/analysis
pip install -r requirements.txt
```

### 功能架构

所有模型在 `__init__` 时预加载，使用 FunASR 全栈语音处理：

| 模块 | 模型 | 功能 |
|------|------|------|
| VAD | fsmn-vad | 人声/非人声检测 |
| ASR | paraformer-zh | 语音转文字（中文准确率极高） |
| 说话人分离 | campplus-cmn | 区分不同角色说话人 |
| 环境音分类 | panns-cnn14-audioset | 识别音乐/打斗/爆炸等非对话段 |

### API 使用示例

```python
from audio_analyzer import AudioAnalyzer

# 初始化（自动检测CUDA）
analyzer = AudioAnalyzer(device="cuda")

# 全流程分析
result = analyzer.analyze_full("天下第一纨绔/第1集.mp4")

# result 结构
{
  "dialogue": [
    {
      "speaker": "spk0",
      "text": "你敢打我？",
      "start": 25.5,
      "end": 28.2
    }
  ],
  "total_speech_segments": 120
}
```

**重要**: 分析服务不会清空或重建 `drama.json`，因为分析结果存储在独立的 `analysis_results.json` 中，即使Express服务重启或扫描也不会丢失。

## 成本估算

- 每集抽帧: 30帧
- 每帧分析费用: ~¥0.012
- 每集费用: ~¥0.36
- 每剧（22集）费用: ~¥7.92
