# 短剧播放闭环项目

基于 React + Express + lowdb + Redis 的短剧播放平台，集成 AI 分析引擎实现自动高光检测与打标。

---

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Node.js | >= 18 | 前后端运行 |
| Python | >= 3.10 | AI 分析引擎 |
| ffmpeg | 系统安装 | 视频抽帧、时长提取 |
| Redis | 6+ (可选) | 缓存层，不装自动降级 lowdb |

---

## 快速上手（5 分钟）

### 1. 安装依赖

```bash
# 前端
cd client && npm install

# 后端
cd ../server && npm install

# AI 引擎（用 glm-4 环境）
conda activate glm-4
pip install openai funasr modelscope torch networkx
```

### 2. 配置环境变量

编辑 `server/.env`（已提供模板，JWT_SECRET 已自动生成）：

```env
JWT_SECRET=your-secret-key
PORT=3001
DOUBAO_API_KEY=your-ark-api-key      # 火山方舟 API Key（必填，否则 AI 不可用）
DOUBAO_EP=doubao-1.5-vision-pro-32k  # 模型端点 ID
```

### 3. 放置视频文件

```
D:\video_data\
├── videos\
│   ├── 北派寻宝笔记\
│   │   ├── 第63集.mp4
│   │   └── 第64集.mp4
│   └── 天下第一纨绔\
│       └── 第1集.mp4
└── pictures\
    ├── 北派寻宝笔记.jpg
    └── 天下第一纨绔.png
```

> 短剧名 = 子目录名，剧集号 = 文件名排序。封面按短剧名前缀匹配。

### 4. 启动

```bash
# 终端 1：启动后端
cd server && npm start          # http://localhost:3001

# 终端 2：启动前端
cd client && npm run dev        # http://localhost:5173
```

打开浏览器访问 `http://localhost:5173`，即可看到短剧列表并播放。

### 5. （可选）启动 AI 高光分析

```bash
conda activate glm-4
cd server/analysis

# 分析指定短剧的全部集
python run_analysis.py --drama 天下第一纨绔

# 后台监控新视频自动分析
python watcher.py
```

分析完成后高光点自动推送至后端，播放器进度条上出现红色高光标记。

---

## 架构一览

```
浏览器 (React 18 + HLS.js)
  |  HTTP /api/*
  v
Express 4 (:3001) ─── lowdb 7 (drama.json)
  |                     |
  + Redis 6+ (缓存)     + highlights 持久化
  |                     |
  + 视频流 (Range 206)  + 30s 自动扫描视频目录
  |
  ^ POST /internal/highlights
  |
AI 分析引擎 (Python)
  双通道抽帧 -> FunASR 音频 -> 豆包 VL/LLM -> 四维高光 -> 推送后端
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| **前端** | React 18, TypeScript 5.3, Vite 5, TailwindCSS 3, HLS.js 1.4 |
| **后端** | Express 4, JWT+bcrypt, helmet, Range 流媒体 (206) |
| **数据库** | lowdb 7 (JSON 持久化), Redis 6+ (缓存层，可选) |
| **AI 引擎** | Python 3.12, FunASR 1.3.9, 豆包 VL/LLM (OpenAI 兼容), ffmpeg |

详细技术文档见 [docs/项目技术文档.md](docs/项目技术文档.md)。

---

## 项目结构

```
project/
├── client/                     # React 前端 (ESM)
│   └── src/
│       ├── components/         # VideoPlayer, DramaList, AuthModal
│       ├── pages/              # PlayPage
│       ├── context/            # AuthContext
│       └── services/           # api.ts (Axios)
│
├── server/                     # Express 后端 (CommonJS)
│   ├── app.js                  # 主入口 (~800 行，全部路由)
│   ├── redis.js                # Redis 客户端 + 降级
│   ├── .env                    # 环境变量
│   ├── database/drama.json     # lowdb 数据文件
│   ├── analysis/               # Python AI 分析引擎
│   │   ├── run_analysis.py     # 主入口
│   │   ├── watcher.py          # 视频目录监控
│   │   ├── graph_builder.py    # 时间轴融合 + 高光检测 + 名称聚类
│   │   ├── multimodal_analyzer.py  # VL 帧分析 + 帧缓存
│   │   ├── audio_analyzer.py   # FunASR 管线
│   │   ├── structured_extractor.py # LLM 结构化提取
│   │   ├── speaker_identifier.py   # 说话人识别
│   │   ├── video_preprocessor.py   # ffmpeg 抽帧
│   │   ├── storage.py          # 持久化 + 断点续传
│   │   └── config.py           # 集中配置
│   └── public/covers/          # 封面备用目录
│
├── docs/                       # 文档
│   └── 项目技术文档.md
│
└── README.md
```

---

## API 接口

### 前端使用

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/dramas` | GET | 短剧列表 |
| `/api/dramas/:id` | GET | 短剧详情 |
| `/api/episodes/:dramaId` | GET | 剧集列表 |
| `/api/episodes/:episodeId/highlights` | GET | 高光点 (?full=true 返回完整区间) |
| `/api/video/:dramaName/:filename` | GET | 视频流 (Range 请求) |
| `/covers/:filename` | GET | 封面图片 |
| `/api/history` | POST | 保存播放记录 |
| `/api/history/:drama_id` | GET | 获取播放记录 |

### 用户认证

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 注册 |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/refresh` | POST | 刷新 Token |
| `/api/auth/logout` | POST | 退出 |
| `/api/user/profile` | GET/PUT | 用户信息 |

### 内部接口（AI 引擎调用）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/internal/highlights` | POST | 写入高光 `{episode_id, points, intervals}` |
| `/internal/highlights/:episodeId` | DELETE | 删除高光 |

---

## AI 分析 CLI

```bash
cd server/analysis

# 分析指定剧
python run_analysis.py --drama 天下第一纨绔

# 分析单独一集
python run_analysis.py --video-url "天下第一纨绔/第1集.mp4"

# 断点续传（跳过已完成剧集）
python run_analysis.py --drama 天下第一纨绔 --resume

# 强制全量重分析
python run_analysis.py --drama 天下第一纨绔 --force

# 后台自动监控
python watcher.py
```

分析结果存放在 `server/database/analysis_{剧名}.json`，高光自动 POST 到后端。

---

## 常见问题

**Q: 没装 Redis 能用吗？**
能。后端启动时 Redis 连接失败自动降级到 lowdb，所有功能正常。

**Q: FunASR 报错怎么办？**
音频分析模块独立容错，单个模型失败不影响整体流程。高光检测会自动退化为纯视觉三维。

**Q: 高光点不显示？**
确认：① AI 分析已完成（`analysis_{剧名}.json` 有数据）；② 后端已启动（接收 POST）；③ 刷新播放页。

**Q: 局域网访问？**
获取本机 IP (`ipconfig`)，其他设备访问 `http://<IP>:5173`。
