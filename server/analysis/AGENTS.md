# 短剧 AI 分析引擎 — 指导文档

> 面向 AI 编码助手。本文档描述 analysis 模块的完整架构、数据流、配置和修改指南。

---

## 架构总览

```
输入: D:\video_data\videos\{剧名}\第N集.mp4
                    │
    ┌───────────────┼───────────────┐
    ▼                               ▼
通道1: 场景抽帧                     通道2: 音频分析 (可选)
extract_key_frames_smart()         AudioAnalyzer.analyze_full()
场景切换检测, 30帧/集               VAD -> ASR -> diarization
    │                               │
    ▼                               ▼
MultimodalAnalyzer               SpeakerIdentifier
analyze_frames_batch()           identify_speakers_for_episode()
多模态VL逐帧分析                     每个spk -> 精准抽帧 -> VL识人
    │                               │
    ├─────────── 汇合 ──────────────┤
    ▼
EpisodeTimeline.build()
音视时间轴融合 -> 高光检测(五维加权)
    │
    ▼
StructuredExtractor.extract_summary()
LLM结构化提取(人物/关系/场景)
    │
    ▼
GraphBuilder.build_episode_graph()
人物关系图谱 -> 全局图谱合并
    │
    ▼
输出: analysis_results.json + timeline_*.json + character_graph_global.json
```

---

## 文件职责

| 文件 | 职责 | 核心类/函数 | 行数 |
|------|------|------------|------|
| `config.py` | 全局配置：路径、模型、API密钥、抽帧参数 | `Config` | ~45 |
| `video_preprocessor.py` | FFmpeg封装：抽帧、时间戳精准抽帧、临时清理 | `VideoPreprocessor` | ~170 |
| `multimodal_analyzer.py` | VL多模态分析 + 帧缓存 + 说话人识别 | `MultimodalAnalyzer`, `FrameCache` | ~220 |
| `structured_extractor.py` | LLM结构化提取：人物/关系/场景/摘要 | `StructuredExtractor` | ~150 |
| `graph_builder.py` | 时间轴融合 + 高光检测 + 人物关系图 + 名称聚类 | `EpisodeTimeline`, `GraphBuilder` | ~400 |
| `audio_analyzer.py` | FunASR音频分析：VAD/ASR/diarization/环境音 | `AudioAnalyzer` | ~230 |
| `speaker_identifier.py` | ASR驱动说话人识别 + 跨集合并 | `SpeakerIdentifier` | ~150 |
| `char_speaker_aligner.py` | 备用：视觉人物 <-> 音频说话人对齐 (OpenAI格式) | `CharacterSpeakerAligner` | ~130 |
| `storage.py` | JSON持久化 + 状态追踪(resume用) | `AnalysisStorage` | ~100 |
| `main.py` | CLI入口，编排全流程 | `analyze_episode()`, `main()` | ~220 |

---

## 配置项 (config.py)

```python
# === 路径 ===
Config.VIDEO_DIR          # D:\video_data\videos\
Config.OUTPUT_DIR         # 输出目录
Config.FRAME_DIR          # 抽帧临时目录 (用完自动清理)
Config.LOWDB_PATH         # drama.json 路径

# === 模型 ===
Config.ACTIVE_MODEL_PROVIDER  # "doubao" (当前)
Config.DOUBAO_API_KEY         # 从环境变量 DOUBAO_API_KEY
Config.DOUBAO_BASE_URL        # https://ark.cn-beijing.volces.com/api/v3
Config.DOUBAO_VL_MODEL        # 视觉模型 -> 环境变量 DOUBAO_EP
Config.DOUBAO_LLM_MODEL       # 语言模型 -> 环境变量 DOUBAO_EP

# === 抽帧 ===
Config.FRAMES_PER_EPISODE     # 30 (场景检测模式)
Config.FRAME_INTERVAL_SECONDS # 5

# === 音频 ===
Config.AUDIO_ENABLED          # True -> 启动ASR+说话人识别
Config.AUDIO_DEVICE           # "cuda" / "cpu"
```

### 环境变量 (server/.env)

```bash
DOUBAO_API_KEY=your-ark-api-key
DOUBAO_EP=doubao-1.5-vision-pro-32k   # 多模态模型endpoint ID
JWT_SECRET=...
PORT=3001
```

---

## 核心数据流

### 1. 场景抽帧 -> VL分析

```
VideoPreprocessor.extract_key_frames_smart(video_path, output_dir, num_frames=30)
  -> ffmpeg select='gt(scene,0.3)'  场景切换检测
  -> 帧数 < 5 -> fallback extract_key_frames()  普通抽帧
  -> 返回 [frame_001.jpg, frame_002.jpg, ...]

MultimodalAnalyzer.analyze_frame(image_path)
  -> FrameCache.get(hash) -> 命中则跳过API调用
  -> OpenAI vision API -> 提取JSON
  -> FrameCache.set(hash, result) -> 写入缓存
  -> 返回 {scene_description, characters, key_event, ...}
```

### 2. 时间轴融合 -> 高光

```
EpisodeTimeline.build(audio_segments, frame_analyses, frame_interval, duration)
  │
  ├─ _score_audio_emotion()  关键词+标点+长度 -> 0-1情绪分
  ├─ _score_visual_change()  字重叠率+场景切换词 -> 0-1变化分
  ├─ _merge_timeline()       1秒网格对齐音视
  ├─ _compute_highlight_score()
  │   score = 0.35 x 音频情绪 + 0.25 x 画面变化 + 0.20 x (音x视)同步
  │         + 0.15 x 对话密度 + 0.05 x 关键词触发
  │
  └─ _extract_highlights()   top-K + 合并相邻(<10s) + 按时间排序
```

### 3. 人物名称聚类

```
GraphBuilder.cluster_character_names(["张三","三哥","张三哥","小张"])
  │
  ├─ 规则1: 完全一致 -> 合并
  ├─ 规则2: _strip_honorifics() -> 剥离小/老/阿/哥/总/大人/姑娘...
  │         核心名相同 -> 合并(较短者作规范名)
  ├─ 规则3: 核心名字串包含 -> 合并 (2字名 != 以它开头的长名)
  ├─ 规则4: 编辑距离 > 0.6 -> 合并
  └─ 规则5: 同姓双名 vs 同姓双名 -> 不合并(张伟明 != 张伟强)
```

### 4. 缓存与断点续传

```
FrameCache (P1):
  键 = SHA256(frame_path)[:16] + ":" + model_name
  存储 = Config.CACHE_DIR/frame_cache.json
  命中 = 跳过API调用

AnalysisStorage (P2a):
  状态机: pending -> in_progress -> completed
  --resume: 跳过 completed，重跑 in_progress/failed
  --force: 忽略状态，强制重跑
```

---

## CLI 用法

```bash
cd server/analysis

# 分析全部剧集(断点续传)
python main.py --all --resume

# 分析指定剧集
python main.py --video-url "D:\\video_data\\videos\\北派寻宝笔记\\第66集.mp4"

# 分析指定剧的所有集
python main.py --drama "天下第一纨绔"

# 强制重新分析(忽略缓存和状态)
python main.py --all --force

# 查看统计
python main.py --stats

# 不启用音频分析
# 设置 Config.AUDIO_ENABLED = False 或缺少 funasr 依赖时自动跳过
```

---

## 输出文件

| 文件 | 内容 |
|------|------|
| `database/analysis_results.json` | 每集的结构化分析 (按 video_url 索引) |
| `database/timeline_{video_url}.json` | 每集的时间轴 (秒级) + 高光区间 |
| `database/speaker_identities.json` | 说话人识别结果 (spk->角色映射) |
| `database/character_graph_global.json` | 全局人物关系图谱 (NetworkX node-link) |
| `database/drama.json` | 剧集元数据 (由 Express 后端维护) |

---

## 修改指南

### 改抽帧策略
`video_preprocessor.py` — 三个方法可选:
- `extract_key_frames()` — 均匀间隔
- `extract_fixed_interval_frames()` — 固定秒数间隔
- `extract_key_frames_smart()` — 场景切换检测 (当前)

在 `main.py:analyze_episode()` 中切换调用。

### 改高光权重
`graph_builder.py:EpisodeTimeline.HIGHLIGHT_WEIGHTS` — 五个权重，和为1.0即可。

### 改高光关键词
`graph_builder.py:EpisodeTimeline.EMOTION_KEYWORDS` — 列表格式 `[(词, 权重), ...]`。

### 改称呼剥离规则
`graph_builder.py:GraphBuilder.HONORIFIC_PREFIXES / HONORIFIC_SUFFIXES`。

### 加新模型
`config.py` — 添加新的 `XXX_API_KEY/XXX_BASE_URL/XXX_MODEL` 配置组。
`main.py` — 在 `main()` 中添加 provider 选择分支。

### 调试技巧
- 设置 `Config.AUDIO_ENABLED = False` 跳过音频分析，加速调试
- `--resume` 模式 + 帧缓存 = 重跑几乎零成本
- 查看 `frame_cache.json` 了解缓存命中情况

---

## 依赖

```
pip install openai funasr modelscope torch networkx
```

可选 (已有降级):
- `funasr` — 音频分析，缺失时自动跳过
- `networkx` — 人物关系图，缺失时只影响图谱功能
- Redis — 缓存层 (Express 后端用，analysis 模块不依赖)

---

## 已知限制

1. **单集分析内存**: 30帧 + 音频全量加载，长集(>30分钟)需注意内存
2. **VL调用成本**: 30帧/集 x 0.012元/帧 ~ 0.36元/集，帧缓存可降为0
3. **人物聚类边界**: "王总->王建国"类合并需LLM辅助 (`cluster_with_llm`)
4. **跨集人物对齐**: 依赖 speaker_identifier 的 spk 映射，纯VL无音频时退化
5. **视频格式**: 仅测试过 mp4，其他格式依赖 ffmpeg 兼容性
