# 短剧视频AI理解与剧情图谱构建方案

## 一、项目概述

### 1.1 目标
- 通过调用AI多模态大模型对视频内容进行理解和总结
- 将视频中的剧情用图的形式构建，支持跨剧集的人物关系连接
- 与现有React动画框架无缝集成，通过metadata注入方式增强视频元数据

### 1.2 设计原则
- **独立性**：视频解析模块可独立运行，不依赖前端
- **兼容性**：解析结果通过标准metadata格式注入，不破坏现有接口
- **可扩展性**：支持增量解析，支持多模态模型切换
- **可观测性**：完整记录解析过程和置信度信息

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      短剧播放闭环系统                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │
│  │   前端 React │◄────►│   Express   │◄────►│   Python    │    │
│  │   (动画层)   │      │   (API层)    │      │   (解析层)   │    │
│  └─────────────┘      └─────────────┘      └─────────────┘    │
│         │                     │                     │          │
│         │              ┌──────┴──────┐              │          │
│         │              ▼             ▼              │          │
│         │        ┌─────────┐  ┌─────────┐          │          │
│         │        │  Redis  │  │  lowdb  │          │          │
│         │        └─────────┘  └─────────┘          │          │
│         │                                           │          │
│         │              ┌─────────────┐              │          │
│         │              │   图数据库   │              │          │
│         │              │  (Neo4j/    │              │          │
│         │              │   NetworkX) │              │          │
│         │              └─────────────┘              │          │
│         │                                           │          │
└─────────┴───────────────────────────────────────────┴──────────┘
```

### 2.2 模块划分

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| 视频解析服务 | Python 3.10+ | 调用多模态模型，提取视频语义信息 |
| 图数据库 | Neo4j / NetworkX | 存储剧情图谱和人物关系 |
| API网关 | Express | 提供metadata注入接口 |
| 前端展示 | React | 剧情图谱可视化 |
| 动画层 | React + CSS | 增强型高光动画 |

## 三、数据模型设计

### 3.1 视频Metadata扩展

```typescript
interface VideoMetadata {
  // 现有字段
  id: number;
  drama_id: number;
  title: string;
  video_url: string;
  
  // 新增：AI解析字段
  ai_analysis?: {
    summary: string;                    // 剧情摘要
    key_scenes: KeyScene[];             // 关键场景
    characters: Character[];             // 人物列表
    relationships: Relationship[];       // 人物关系
    timeline: TimelineEvent[];           // 时间线事件
    themes: string[];                   // 主题标签
    sentiment_curve: SentimentPoint[];   // 情感曲线
    confidence_score: number;            // 解析置信度
    analyzed_at: string;                 // 解析时间
  };
}

interface KeyScene {
  timestamp: number;                    // 场景时间戳（秒）
  description: string;                  // 场景描述
  importance: 'low' | 'medium' | 'high' | 'critical';
  tags: string[];                       // 场景标签
}

interface Character {
  id: string;                           // 人物唯一标识
  name: string;                         // 人物名称
  role: 'protagonist' | 'antagonist' | 'supporting' | 'minor';
  description: string;                  // 人物简介
  first_appearance: number;              // 首次出现时间
  appearances: number[];                // 出现集数列表
  attributes: Record<string, any>;      // 人物属性
}

interface Relationship {
  source_id: string;                    // 源人物ID
  target_id: string;                    // 目标人物ID
  type: string;                         // 关系类型
  episodes: number[];                   // 关系出现集数
  strength: number;                     // 关系强度 0-1
  description: string;                 // 关系描述
}

interface TimelineEvent {
  timestamp: number;                    // 事件时间戳
  episode: number;                      // 所属集数
  title: string;                        // 事件标题
  description: string;                  // 事件描述
  participants: string[];               // 参与者
  event_type: 'plot_twist' | 'conflict' | 'revelation' | 'milestone';
  emotional_impact: number;              // 情感冲击度 0-10
}

interface SentimentPoint {
  timestamp: number;                   // 时间戳
  sentiment: number;                    // 情感值 -1 to 1
  category: 'joy' | 'sadness' | 'anger' | 'fear' | 'surprise' | 'neutral';
}
```

### 3.2 图数据库模型（Neo4j）

```cypher
# 节点类型
(:Drama {id, title, description, total_episodes})
(:Episode {id, episode_number, title, summary})
(:Character {id, name, role, description})
(:Scene {id, timestamp, description, importance})
(:Event {id, title, description, event_type, emotional_impact})

# 关系类型
(:Character)-[:APPEARS_IN {episodes: [], strength: 0}]->(:Episode)
(:Character)-[:RELATES_TO {type, episodes: [], strength: 0}]->(:Character)
(:Character)-[:PARTICIPATES_IN]->(:Event)
(:Event)-[:HAPPENS_AT {timestamp}]->(:Scene)
(:Episode)-[:CONTAINS]->(:Scene)
(:Episode)-[:FOLLOWS]->(:Episode)
(:Drama)-[:HAS_EPISODE]->(:Episode)
```

### 3.3 人物关系图谱数据结构

```python
class CharacterRelationshipGraph:
    """人物关系图谱"""
    
    def __init__(self):
        self.characters: Dict[str, Character] = {}
        self.relationships: List[Relationship] = []
        self.drama_id: Optional[int] = None
    
    def add_character(self, character: Character):
        """添加人物节点"""
        pass
    
    def add_relationship(self, relationship: Relationship):
        """添加人物关系"""
        pass
    
    def get_character_network(self, character_id: str, depth: int = 2) -> Dict:
        """获取指定人物的社交网络"""
        pass
    
    def get_relationship_path(self, source: str, target: str) -> List[Relationship]:
        """获取两个人物之间的关系路径"""
        pass
```

## 四、视频解析流程

### 4.1 解析pipeline设计

```
视频文件 (.mp4)
    │
    ▼
┌─────────────────┐
│  视频预处理      │
│  - 抽帧采样      │
│  - 音频提取      │
│  - 场景分割      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  多模态理解      │
│  - 关键帧分析    │
│  - 音频转文本    │
│  - 场景理解      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  结构化提取      │
│  - 人物识别      │
│  - 关系抽取      │
│  - 事件抽取      │
│  - 情感分析      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  图谱构建        │
│  - 节点去重      │
│  - 关系推理      │
│  - 时序对齐      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  结果输出        │
│  - JSON metadata │
│  - Neo4j存储     │
│  - 缓存更新      │
└─────────────────┘
```

### 4.2 视频预处理模块

```python
class VideoPreprocessor:
    """视频预处理"""
    
    def __init__(self, config: PreprocessorConfig):
        self.frame_sample_rate = config.get('frame_sample_rate', 1)  # 每秒抽帧数
        self.scene_threshold = config.get('scene_threshold', 30.0)    # 场景切换阈值
        self.audio_format = config.get('audio_format', 'wav')
    
    def extract_frames(self, video_path: str, output_dir: str) -> List[str]:
        """
        抽帧采样
        
        策略:
        - 均匀采样: 每N秒抽一帧
        - 关键帧检测: 使用帧差分检测场景切换点
        - 自适应采样: 情节紧张时提高采样率
        
        Returns:
            帧图片路径列表
        """
        pass
    
    def extract_audio(self, video_path: str, output_path: str) -> str:
        """提取音频流"""
        pass
    
    def detect_scenes(self, video_path: str) -> List[SceneSegment]:
        """
        场景分割
        
        Returns:
            场景片段列表，每个片段包含起止时间
        """
        pass
    
    def get_key_frames(self, video_path: str, num_frames: int = 30) -> List[KeyFrame]:
        """
        提取关键帧
        
        关键帧选择策略:
        1. 场景首帧
        2. 镜头切换帧
        3. 包含文字的帧
        4. 画面突变帧
        """
        pass
```

### 4.3 多模态理解模块

```python
class MultimodalAnalyzer:
    """多模态内容理解"""
    
    def __init__(self, config: AnalyzerConfig):
        # 可配置使用不同模型
        self.video_model = self._init_video_model(config.video_model)
        self.audio_model = self._init_audio_model(config.audio_model)
        self.ocr_model = self._init_ocr_model(config.ocr_model)
    
    async def analyze_frame(self, frame: np.ndarray) -> FrameAnalysis:
        """
        单帧分析
        
        返回:
        - 场景描述
        - 人物位置和数量
        - 文字内容（OCR）
        - 物体和动作
        """
        pass
    
    async def analyze_video_segment(
        self, 
        frames: List[np.ndarray],
        audio_segment: bytes
    ) -> SegmentAnalysis:
        """
        视频片段分析（多帧+音频）
        
        综合分析:
        - 动作序列理解
        - 对话内容（ASR + NLP）
        - 情感推断
        - 关键事件识别
        """
        pass
    
    def transcribe_audio(self, audio_path: str) -> TranscriptionResult:
        """
        音频转文本
        
        输出:
        - 时间戳对齐的文本
        - 说话人识别
        - 音频质量评估
        """
        pass
```

### 4.4 结构化信息抽取模块

```python
class StructuredExtractor:
    """结构化信息抽取"""
    
    def __init__(self, config: ExtractorConfig):
        self.ner_model = self._init_ner_model()
        self.relation_model = self._init_relation_model()
        self.sentiment_model = self._init_sentiment_model()
    
    def extract_characters(
        self, 
        frames: List[FrameAnalysis],
        dialogue: TranscriptionResult
    ) -> List[Character]:
        """
        人物识别与抽取
        
        方法:
        1. 视觉特征聚类（同一人物外观特征）
        2. 名字识别（OCR + NER）
        3. 角色分配（主角/配角/反派）
        4. 去重与合并
        
        Returns:
            识别的人物列表
        """
        pass
    
    def extract_relationships(
        self,
        characters: List[Character],
        frames: List[FrameAnalysis],
        dialogue: TranscriptionResult,
        timeline: List[TimelineEvent]
    ) -> List[Relationship]:
        """
        关系抽取
        
        关系类型:
        - 家族关系: 父子、夫妻、兄弟
        - 社会关系: 朋友、敌人、上下级
        - 情感关系: 喜欢、讨厌、羡慕
        - 事件关系: 对手、盟友、背叛者
        
        抽取方法:
        1. 显式关系: 对话中直接提到
        2. 隐式关系: 行为推断（眼神、肢体语言）
        3. 时序关系: 事件发生的先后顺序
        
        Returns:
            人物关系列表
        """
        pass
    
    def extract_events(
        self,
        frames: List[FrameAnalysis],
        dialogue: TranscriptionResult
    ) -> List[TimelineEvent]:
        """
        事件抽取
        
        事件类型:
        - plot_twist: 剧情转折
        - conflict: 冲突对抗
        - revelation: 揭示揭露
        - milestone: 里程碑事件
        
        Returns:
            时间线事件列表
        """
        pass
    
    def analyze_sentiment(
        self,
        frames: List[FrameAnalysis],
        dialogue: TranscriptionResult
    ) -> List[SentimentPoint]:
        """
        情感曲线分析
        
        分析维度:
        - 视觉情感: 画面氛围、颜色、表情
        - 语言情感: 文本情感极性
        - 音频情感: 语速、音调
        
        Returns:
            情感曲线点列表
        """
        pass
```

### 4.5 图谱构建与推理模块

```python
class GraphBuilder:
    """剧情图谱构建"""
    
    def __init__(self, config: GraphBuilderConfig):
        self.graph_db = Neo4jConnection(config.neo4j_uri)
        self.cache = RedisConnection(config.redis_url)
    
    def build_character_network(
        self,
        characters: List[Character],
        relationships: List[Relationship]
    ) -> CharacterRelationshipGraph:
        """
        构建人物关系网络
        
        处理:
        1. 节点去重与合并
        2. 关系强度计算
        3. 间接关系推断
        4. 关系时序标注
        """
        pass
    
    def infer_implicit_relationships(
        self,
        characters: List[Character],
        events: List[TimelineEvent]
    ) -> List[Relationship]:
        """
        推断隐式关系
        
        推断规则:
        1. 共同参与同一事件 -> 潜在关联
        2. 事件对抗双方 -> 对立关系
        3. 连续事件主角 -> 成长/转变关系
        """
        pass
    
    def align_cross_episode_characters(
        self,
        episode_graphs: List[CharacterRelationshipGraph]
    ) -> Dict[str, str]:
        """
        跨剧集人物对齐
        
        匹配策略:
        1. 外观相似度（视觉特征）
        2. 名字匹配（模糊匹配）
        3. 关系网络相似度
        4. 首次出场场景相似度
        
        Returns:
            跨剧集人物ID映射
        """
        pass
    
    def save_to_neo4j(self, graph: CharacterRelationshipGraph):
        """保存到图数据库"""
        pass
```

## 五、与现有框架的集成方案

### 5.1 Metadata注入机制

```
解析完成 → Metadata构建 → API存储 → 前端获取 → 动画增强
```

#### 5.1.1 存储层设计

```python
# server/database/drama.json 扩展

{
  "dramas": [...],
  "episodes": [
    {
      "id": 1,
      "drama_id": 1,
      "title": "第1集",
      "video_url": "...",
      // 新增: AI分析结果
      "ai_analysis": {
        "summary": "...",
        "characters": [...],
        "relationships": [...],
        "timeline": [...],
        "sentiment_curve": [...],
        "confidence_score": 0.85,
        "analyzed_at": "2026-05-22T10:00:00Z"
      }
    }
  ],
  "play_history": [...],
  "character_graphs": {
    // 跨剧集人物关系图
    "global": {
      "characters": [...],
      "relationships": [...]
    }
  }
}
```

#### 5.1.2 API接口设计

```javascript
// 新增API端点

// 触发视频解析
POST /api/analysis/analyze
{
  "episode_id": 123,
  "options": {
    "extract_characters": true,
    "extract_relationships": true,
    "extract_timeline": true,
    "force_refresh": false
  }
}

// 获取分析结果
GET /api/analysis/:episodeId

// 批量获取剧集分析（用于剧集对比）
POST /api/analysis/batch
{
  "episode_ids": [1, 2, 3, 4]
}

// 获取人物关系图谱
GET /api/analysis/:episodeId/character-graph
GET /api/analysis/drama/:dramaId/global-graph  // 跨剧集图谱

// 获取情感曲线（用于动画增强）
GET /api/analysis/:episodeId/sentiment
```

### 5.2 动画接口扩展

#### 5.2.1 React端数据结构

```typescript
// 新增: 剧情增强动画接口

interface DramaEnhancementConfig {
  // 基础高光点（现有）
  highlights: number[];
  
  // 新增: 剧情增强数据
  scenes?: {
    timestamp: number;
    importance: 'low' | 'medium' | 'high' | 'critical';
    type: 'dialogue' | 'action' | 'revelation' | 'climax';
  }[];
  
  sentiment_curve?: {
    timestamp: number;
    intensity: number;  // 0-1, 情感强度
  }[];
  
  // 高能预警配置
  alert_config?: {
    enabled: boolean;
    trigger_before: number;  // 高能前几秒触发预警
    min_intensity: number;   // 最小情感强度阈值
  };
}

// 组件API扩展
<VideoPlayer
  highlights={highlights}
  // 新增
  dramaEnhancement={dramaEnhancementConfig}
  onSceneHighlight={(scene) => {/* 自定义场景高亮 */}}
  onSentimentChange={(sentiment) => {/* 情感变化回调 */}}
/>
```

#### 5.2.2 动画增强实现

```typescript
// 情感驱动的动画强度

const getAnimationIntensity = (sentiment: number): AnimationConfig => {
  // sentiment: -1 (悲伤) to 1 (欢乐)
  const absSentiment = Math.abs(sentiment);
  
  if (absSentiment < 0.3) {
    return { particleCount: 4, flashIntensity: 0.3, shakeAmplitude: 2 };
  } else if (absSentiment < 0.6) {
    return { particleCount: 8, flashIntensity: 0.6, shakeAmplitude: 4 };
  } else {
    return { particleCount: 16, flashIntensity: 1.0, shakeAmplitude: 8 };
  }
};

// 剧情转折点动画

const handlePlotTwist = (event: TimelineEvent) => {
  if (event.event_type === 'plot_twist') {
    // 1. 屏幕闪白
    triggerFlash({ intensity: 1.0, duration: 500 });
    
    // 2. 画面震动
    triggerShake({ amplitude: 8, duration: 300 });
    
    // 3. 粒子爆发
    emitParticles({ count: 20, emoji: '🤯', burst: true });
    
    // 4. 显示剧情标签
    showToast({ 
      message: event.title, 
      duration: 3000,
      style: 'highlight'
    });
  }
};
```

## 六、实现步骤

### 6.1 Phase 1: 基础框架搭建

**目标**: 搭建Python解析服务基础框架

**任务清单**:
1. [ ] 项目结构初始化
   - 创建 `server/python/` 目录
   - 配置虚拟环境和依赖
   - 搭建日志系统

2. [ ] 视频预处理模块
   - 实现FFmpeg集成
   - 实现帧采样
   - 实现音频提取

3. [ ] 基础API服务
   - FastAPI框架搭建
   - 任务队列集成（Celery/Redis Queue）
   - 解析状态查询接口

**产出物**:
- 可独立运行的视频解析服务
- 基础API文档

### 6.2 Phase 2: 核心解析逻辑

**目标**: 实现多模态内容理解

**任务清单**:
1. [ ] 多模态模型集成
   - 视频理解模型（Qwen-VL / GPT-4V / Gemini）
   - ASR模型（Whisper）
   - OCR模型

2. [ ] 结构化抽取
   - 人物识别与去重
   - 关系抽取
   - 事件抽取
   - 情感分析

3. [ ] 结果验证
   - 抽样人工验证
   - 置信度评估

**产出物**:
- 解析准确率基线
- 错误分析报告

### 6.3 Phase 3: 图谱系统

**目标**: 构建人物关系图谱

**任务清单**:
1. [ ] 图数据库选型与部署
   - Neo4j或NetworkX+SQLite
   - 数据导入脚本

2. [ ] 图谱构建算法
   - 节点去重算法
   - 关系推断算法
   - 跨剧集对齐算法

3. [ ] 图谱查询API
   - 人物网络查询
   - 关系路径查询
   - 社区发现

**产出物**:
- 人物关系图谱数据库
- 图谱可视化Demo

### 6.4 Phase 4: 前端集成

**目标**: 与React动画层集成

**任务清单**:
1. [ ] API对接
   - Express路由扩展
   - Metadata存储集成
   - 缓存策略

2. [ ] 前端组件开发
   - DramaEnhancementProvider
   - 剧情图谱可视化组件
   - 增强型高光动画

3. [ ] 用户体验优化
   - 加载状态优化
   - 降级策略
   - 错误提示

**产出物**:
- 完整的剧情增强功能
- 用户使用文档

### 6.5 Phase 5: 优化与扩展

**目标**: 性能优化和功能扩展

**任务清单**:
1. [ ] 性能优化
   - 并行解析优化
   - 缓存策略优化
   - 增量解析支持

2. [ ] 模型优化
   - Prompt工程优化
   - 结果后处理优化
   - 领域适应

3. [ ] 扩展功能
   - 多语言支持
   - 实时解析（直播场景）
   - 用户反馈闭环

**产出物**:
- 优化后的解析系统
- 扩展功能Demo

## 七、技术选型建议

### 7.1 多模态模型

| 模型 | 优势 | 劣势 | 推荐场景 |
|------|------|------|----------|
| Qwen-VL | 开源、中文理解好 | 视频理解有限 | 优先推荐 |
| GPT-4V | 理解能力强 | 成本高、限速 | 高质量需求 |
| Gemini Pro | 多模态统一 | 国内访问受限 | 探索阶段 |
| CogVLM | 中文开源 | 视频能力弱 | 备选方案 |

### 7.2 图数据库

| 方案 | 优势 | 劣势 | 推荐场景 |
|------|------|------|----------|
| Neo4j | 功能强大、查询灵活 | 部署复杂、资源占用高 | 生产环境 |
| NetworkX + SQLite | 轻量、部署简单 | 查询能力有限 | 开发/小规模 |
| Dgraph | 分布式支持 | 社区较小 | 大规模部署 |

### 7.3 任务队列

| 方案 | 优势 | 劣势 | 推荐场景 |
|------|------|------|----------|
| Celery + Redis | 功能完整 | 配置复杂 | 生产环境 |
| RQ (Redis Queue) | 简单轻量 | 功能有限 | 小规模 |
| FastAPI后台任务 | 集成度高 | 持久化弱 | 简单场景 |

## 八、数据存储方案

### 8.1 存储层次

```
┌─────────────────────────────────────────────────────┐
│                   存储层次设计                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  热数据层 (Redis)                                    │
│  - 当前解析任务状态                                  │
│  - 高频访问的metadata                                │
│  - 缓存的图谱查询结果                                │
│  TTL: 1小时 - 1天                                   │
│                                                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  温数据层 (lowdb/JSON)                              │
│  - 解析完成的metadata                                │
│  - 人物关系数据                                      │
│  - 剧集信息                                          │
│  与现有lowdb集成                                     │
│                                                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  冷数据层 (文件系统)                                 │
│  - 原始帧图片                                        │
│  - 中间处理结果                                      │
│  - 模型输出日志                                      │
│  定期清理或归档                                      │
│                                                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  图数据层 (Neo4j)                                   │
│  - 人物关系网络                                      │
│  - 事件关联图谱                                      │
│  - 跨剧集人物对齐                                    │
│  独立部署                                            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 8.2 缓存策略

```python
class AnalysisCache:
    """解析结果缓存"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ttl = 3600  # 1小时
    
    def get_cached_result(self, episode_id: int) -> Optional[dict]:
        """获取缓存的解析结果"""
        key = f"analysis:episode:{episode_id}"
        return self.redis.get(key)
    
    def cache_result(self, episode_id: int, result: dict):
        """缓存解析结果"""
        key = f"analysis:episode:{episode_id}"
        self.redis.setex(key, self.ttl, json.dumps(result))
    
    def invalidate(self, episode_id: int):
        """失效缓存"""
        key = f"analysis:episode:{episode_id}"
        self.redis.delete(key)
```

## 九、性能优化考虑

### 9.1 解析加速策略

```python
class ParallelAnalyzer:
    """并行解析加速"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def analyze_video(self, video_path: str) -> AnalysisResult:
        # 1. 预处理并行化
        frames_future = self.executor.submit(self.preprocess.extract_frames, video_path)
        audio_future = self.executor.submit(self.preprocess.extract_audio, video_path)
        
        frames = await frames_future.result()
        audio = await audio_future.result()
        
        # 2. 帧分析并行化（分批）
        frame_batches = self.chunk_list(frames, batch_size=10)
        batch_results = self.executor.map(self.analyze_frame_batch, frame_batches)
        
        # 3. 汇总结果
        return self.aggregate_results(batch_results)
```

### 9.2 增量解析策略

```python
class IncrementalAnalyzer:
    """增量解析"""
    
    def check_need_update(self, episode_id: int, episode_mtime: float) -> bool:
        """检查是否需要重新解析"""
        cached = self.cache.get_cached_result(episode_id)
        if not cached:
            return True
        return cached.get('analyzed_at', 0) < episode_mtime
    
    def get_missing_episodes(self, drama_id: int) -> List[int]:
        """获取未解析的剧集"""
        all_episodes = self.get_episode_list(drama_id)
        analyzed = self.get_analyzed_episodes(drama_id)
        return list(set(all_episodes) - set(analyzed))
```

### 9.3 模型调用优化

```python
class ModelOptimizer:
    """模型调用优化"""
    
    def __init__(self):
        self.request_cache = {}  # LRU cache
        self.batch_buffer = []
        self.batch_size = 16
        self.batch_timeout = 1.0  # 秒
    
    async def smart_batch(self, frame: np.ndarray) -> Any:
        """
        智能批处理
        
        策略:
        1. 等待凑满batch_size
        2. 超时自动执行
        3. 结果缓存（相似帧）
        """
        self.batch_buffer.append(frame)
        
        if len(self.batch_buffer) >= self.batch_size:
            return await self._execute_batch()
        
        # 等待超时
        await asyncio.sleep(self.batch_timeout)
        if self.batch_buffer:
            return await self._execute_batch()
```

## 十、扩展性考虑

### 10.1 模型热切换

```python
class ModelRouter:
    """模型路由"""
    
    def __init__(self):
        self.models = {
            'qwen_vl': QwenVLModel(),
            'gpt4v': GPT4VModel(),
            'gemini': GeminiModel(),
        }
        self.current_model = 'qwen_vl'
    
    def switch_model(self, model_name: str):
        """运行时切换模型"""
        if model_name in self.models:
            self.current_model = model_name
            self.current = self.models[model_name]
    
    def get_model(self, task_type: str) -> Any:
        """根据任务类型选择模型"""
        if task_type == 'character_detection':
            return self.models['qwen_vl']  # 适合人物识别
        elif task_type == 'sentiment_analysis':
            return self.models['gpt4v']     # 适合情感分析
        return self.current
```

### 10.2 插件化抽取器

```python
class ExtractorRegistry:
    """抽取器注册表"""
    
    def __init__(self):
        self.extractors = {}
    
    def register(self, name: str, extractor: BaseExtractor):
        """注册抽取器"""
        self.extractors[name] = extractor
    
    def get_extractor(self, name: str) -> BaseExtractor:
        """获取抽取器"""
        return self.extractors.get(name)
    
    def run_all(self, context: AnalysisContext) -> dict:
        """运行所有抽取器"""
        results = {}
        for name, extractor in self.extractors.items():
            try:
                results[name] = extractor.extract(context)
            except Exception as e:
                logger.error(f"Extractor {name} failed: {e}")
                results[name] = None
        return results
```

### 10.3 Webhook通知机制

```python
class AnalysisWebhook:
    """解析完成Webhook"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def notify(
        self,
        episode_id: int,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ):
        """发送Webhook通知"""
        payload = {
            'episode_id': episode_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
        }
        
        if result:
            payload['result_summary'] = {
                'characters_count': len(result.get('characters', [])),
                'relationships_count': len(result.get('relationships', [])),
                'confidence_score': result.get('confidence_score', 0),
            }
        
        if error:
            payload['error'] = error
        
        await self._send_webhook(payload)
```

## 十一、监控与可观测性

### 11.1 指标收集

```python
class AnalysisMetrics:
    """分析指标"""
    
    def __init__(self, prometheus_client):
        self.client = prometheus_client
        
        # 解析指标
        self.parse_duration = self.client.Histogram(
            'analysis_parse_duration_seconds',
            '解析耗时',
            ['episode_id', 'model']
        )
        
        self.parse_success = self.client.Counter(
            'analysis_parse_success_total',
            '解析成功次数',
            ['model']
        )
        
        self.parse_errors = self.client.Counter(
            'analysis_parse_errors_total',
            '解析错误次数',
            ['error_type']
        )
        
        # 模型调用指标
        self.model_calls = self.client.Counter(
            'analysis_model_calls_total',
            '模型调用次数',
            ['model', 'operation']
        )
        
        self.model_latency = self.client.Histogram(
            'analysis_model_latency_seconds',
            '模型调用延迟',
            ['model', 'operation']
        )
```

### 11.2 日志规范

```python
import structlog

# 结构化日志配置
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# 日志使用示例
logger = structlog.get_logger()

logger.info(
    "analysis_started",
    episode_id=123,
    drama_id=1,
    video_duration=1800,
    model="qwen_vl"
)

logger.warning(
    "low_confidence_detected",
    episode_id=123,
    confidence_score=0.45,
    threshold=0.6
)

logger.error(
    "analysis_failed",
    episode_id=123,
    error_type="model_timeout",
    error_detail="Request timeout after 60s"
)
```

## 十二、安全考虑

### 12.1 API鉴权

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    """验证API密钥"""
    valid_keys = get_valid_api_keys()  # 从配置或数据库获取
    if api_key not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

@app.post("/analysis/analyze", dependencies=[Security(verify_api_key)])
async def analyze_video(request: AnalyzeRequest):
    """分析视频"""
    pass
```

### 12.2 资源限制

```python
class AnalysisRateLimiter:
    """解析限流"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.max_concurrent = 5
        self.daily_limit = 100
    
    async def check_limit(self, user_id: str) -> bool:
        """检查限流"""
        # 检查并发数
        concurrent_key = f"limit:concurrent:{user_id}"
        concurrent = self.redis.get(concurrent_key)
        if concurrent and int(concurrent) >= self.max_concurrent:
            return False
        
        # 检查日限额
        daily_key = f"limit:daily:{user_id}:{date.today()}"
        daily_count = self.redis.get(daily_key)
        if daily_count and int(daily_count) >= self.daily_limit:
            return False
        
        return True
    
    async def acquire(self, user_id: str):
        """获取执行令牌"""
        # 实现令牌桶逻辑
        pass
```

## 十三、测试策略

### 13.1 单元测试

```python
import pytest

class TestStructuredExtractor:
    """结构化抽取器测试"""
    
    def test_character_extraction(self, sample_frames):
        """人物抽取测试"""
        extractor = StructuredExtractor()
        characters = extractor.extract_characters(
            sample_frames,
            sample_transcription
        )
        
        assert len(characters) > 0
        assert all(c.name for c in characters)
        assert all(c.role for c in characters)
    
    def test_relationship_extraction(self, sample_characters):
        """关系抽取测试"""
        extractor = StructuredExtractor()
        relationships = extractor.extract_relationships(
            sample_characters,
            sample_frames,
            sample_transcription
        )
        
        # 验证关系有效性
        for rel in relationships:
            assert rel.source_id != rel.target_id
            assert 0 <= rel.strength <= 1
```

### 13.2 集成测试

```python
class TestAnalysisPipeline:
    """分析管道集成测试"""
    
    async def test_full_pipeline(self, test_video_path):
        """完整解析流程测试"""
        preprocessor = VideoPreprocessor()
        analyzer = MultimodalAnalyzer()
        extractor = StructuredExtractor()
        
        # 1. 预处理
        frames = await preprocessor.extract_frames(test_video_path)
        assert len(frames) > 0
        
        # 2. 分析
        analysis = await analyzer.analyze_frames(frames)
        assert analysis is not None
        
        # 3. 抽取
        characters = extractor.extract_characters(frames, analysis)
        relationships = extractor.extract_relationships(characters, frames)
        
        # 4. 验证结果
        assert len(characters) > 0
        assert len(relationships) > 0
```

## 十四、部署方案

### 14.1 Docker化部署

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 14.2 docker-compose配置

```yaml
version: '3.8'

services:
  analysis-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
      - API_KEY=${API_KEY}
    depends_on:
      - redis
      - neo4j
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: 4

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data
```

## 十五、总结与建议

### 15.1 核心要点

1. **模块独立性**: 解析层完全独立于前端，通过标准API通信
2. **渐进式实现**: 按Phase逐步实现，每个Phase有明确产出
3. **兼容优先**: 保持与现有lowdb/Redis架构的兼容性
4. **可扩展性**: 支持模型热切换、插件化抽取器
5. **可观测性**: 完整的日志、指标、监控体系

### 15.2 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型调用失败 | 解析服务不可用 | 多模型备份、降级策略 |
| 解析结果质量差 | 功能不可用 | 置信度过滤、人工审核 |
| 性能瓶颈 | 用户体验差 | 异步处理、缓存优化 |
| 存储爆炸 | 系统崩溃 | 定期清理、冷热分层 |

### 15.3 后续优化方向

1. **实时解析**: 支持直播/短视频实时分析
2. **个性化**: 基于用户偏好调整动画强度
3. **社交化**: 用户可标注、评论剧情节点
4. **商业化**: 剧情广告植入、IP联动

---

**文档版本**: v1.0  
**更新日期**: 2026-05-22  
**维护者**: AI Development Team
