# 短剧播放闭环项目 — 技术框架文档

## 项目概述

基于 React + Express + lowdb 的短剧视频播放平台，支持局域网部署和多人访问。视频文件来自外部目录，启动时自动扫描并建立索引。

| 维度       | 技术选型                                |
|----------|--------------------------------------|
| 前端框架    | React 18 + TypeScript               |
| 构建工具    | Vite 5                               |
| UI 样式   | TailwindCSS 3 + 自定义暗色主题 CSS 变量     |
| 视频播放器   | HLS.js 1.4（原生 `<video>` 降级）         |
| 路由      | React Router 6                       |
| HTTP 请求 | Axios 1.6                            |
| 后端框架    | Express 4                            |
| 数据库     | lowdb 7（JSON 文件 `database/drama.json`） |
| 安全      | helmet 7 + CORS                      |
| 视频存储    | 外部目录 `D:\video_data\videos\{剧名}\`  |
| 封面存储    | 外部目录 `D:\video_data\pictures\`     |
| 服务端口    | 3001（后端）/ 5173（Vite dev server）    |

---

## 一、整体项目架构

```
┌─────────────────────────┐
│       Web Client        │
│  React + HLS.js 页面     │
└───────────┬─────────────┘
            │ HTTP (Vite proxy /api → localhost:3001)
            │ REST API + Video Stream
            ▼
┌─────────────────────────┐
│      Express Server     │
│     (Node.js :3001)     │
└───────────┬─────────────┘
            │
   ┌────────┴────────┐
   │                 │
   ▼                 ▼
 lowdb JSON       外部视频目录
(drama.json)    D:\video_data\
```

---

## 二、项目组件划分

| 模块     | 职责                       | 实际技术                    |
|--------|--------------------------|-------------------------|
| Web 前端 | 短剧列表、播放页、播放器控制         | React + TypeScript + TailwindCSS + HLS.js |
| API 服务端 | 剧集数据、视频地址、播放记录         | Express + lowdb          |
| 数据层    | JSON 文件存储（dramas + episodes + play_history） | lowdb (`database/drama.json`) |
| 视频源    | 外部视频目录，按短剧名分子目录，启动时自动扫描 | `D:\video_data\videos\`  |
| 封面源    | 外部图片目录，按短剧名前缀匹配        | `D:\video_data\pictures\` |

---

## 三、客户端（Web）设计

### 已采用技术

| 技术     | 选型          | 说明                     |
|--------|-------------|------------------------|
| 前端框架   | React 18    | 函数组件 + Hooks           |
| UI 框架  | TailwindCSS 3 + 自定义 CSS 变量 | 暗色主题，移动端优先            |
| 视频播放器  | HLS.js 1.4  | 支持 m3u8 流，原生 video 降级 |
| 状态管理   | React 内置    | useState + useCallback |
| 请求库    | Axios 1.6   | baseURL: /api           |

### CSS 变量系统（暗色主题）

```css
--bg-primary: #0f0f0f;      /* 页面底色 */
--bg-secondary: #1a1a1a;    /* 次级底色 */
--bg-tertiary: #242424;     /* 三级底色 */
--bg-card: rgba(26,26,26,0.8);      /* 卡片底色 */
--bg-overlay: rgba(0,0,0,0.6);      /* 遮罩层 */
--text-primary: #ffffff;     /* 主文字 */
--text-secondary: rgba(255,255,255,0.7);  /* 次级文字 */
--text-muted: rgba(255,255,255,0.5);      /* 弱化文字 */
--accent-primary: #ff4757;   /* 主强调色（红） */
--accent-secondary: #ffa502; /* 次强调色（橙） */
--accent-success: #2ed573;   /* 成功色（绿） */
--accent-info: #1e90ff;      /* 信息色（蓝） */
--border-color: rgba(255,255,255,0.1);
--touch-target: 44px;        /* 移动端最小触控目标 */
```

---

## 四、前端页面设计

### 1. 短剧列表页 (`DramaList.tsx`)

```
┌──────────────────────────────┐
│ Header: 🎬 短剧播放平台 [首页]  │
├──────────────────────────────┤
│ 短剧列表          [刷新列表]    │
├──────────────────────────────┤
│ ┌────────┐ ┌────────┐       │
│ │ 封面    │ │ 封面    │       │
│ │ 标题    │ │ 标题    │       │
│ │ 描述    │ │ 描述    │       │
│ │ N 集    │ │ N 集    │       │
│ └────────┘ └────────┘       │
└──────────────────────────────┘
```

**实现细节**：
- **30 秒自动轮询**：`setInterval` 每 30 秒静默刷新列表
- **刷新按钮**：手动触发重新加载，显示"刷新中..."状态
- **空状态**：无剧集时提示"请将视频文件放入 D:\\video_data 目录"
- **封面**：通过 `/covers/{filename}` 加载，加载失败显示 SVG 占位图
- **封面 URL 编码**：使用 `encodeURIComponent` 处理中文文件名

### 2. 播放页 (`PlayPage.tsx`)

```
┌──────────────────────────────┐
│        VideoPlayer           │
│   (HLS.js / 原生 video)       │
│                              │
│  [海报 / 首帧回退]             │
│                              │
│  ▶️ ━━━━━━●━━━━ 1:23/5:00 🔊⛶│
├──────────────────────────────┤
│ 剧集信息                       │
├──────────────────────────────┤
│ 剧集列表（缩略图网格）            │
│ ┌───┐ ┌───┐ ┌───┐           │
│ │第1│ │第2│ │第3│  ← 高亮当前  │
│ └───┘ └───┘ └───┘           │
└──────────────────────────────┘
```

**实现细节**：
- **播放进度自动保存**：每 5 秒调用 `POST /api/history`
- **自动续播**：当前集播放结束 → 自动跳转到下一集
- **剧集缩略图提取**：使用 Canvas 从视频截取首帧作为缩略图
- **Mock 剧集降级**：当 episodes 表为空时，根据 drama 的 episode_count 自动生成虚拟剧集列表

---

## 五、播放器技术方案

采用 **HLS.js + 原生 video 降级**，实现完整的状态机管理。

### 状态机模型（8 状态）

```
idle → loading → ready → playing ⇄ paused
                          ↓
                      buffering
                          ↓
                        ended
                     
error（任何状态都可能触发，可恢复错误支持重试）
```

### 核心功能

| 功能       | 实现                              |
|----------|----------------------------------|
| HLS 播放   | 检测 HLS 支持 → 加载 m3u8 → 原生 video 降级 |
| 播放/暂停    | 空格键 / 点击按钮                      |
| 进度条      | 双轨设计：灰色缓冲范围 + 红色播放进度，拖动吸附       |
| 快进/快退    | ← → 键 5 秒步进                      |
| 音量       | ↑ ↓ 键调节 / 拖动滑块                   |
| 静音       | M 键                              |
| 全屏       | F 键 / 点击按钮                       |
| 海报       | poster 属性，视频加载后切换                |
| 缓冲可视化    | 实时读取 `video.buffered` 渲染缓冲区间     |
| 错误恢复     | 可恢复错误显示"重试"按钮                   |
| 缩略图提取    | Canvas 截图，320×180，JPEG 95% 质量    |
| 触控适配    | 44px 最小触控目标，移动端控制栏自动隐藏（3 秒无操作） |

### 播放链路

```
前端 VideoPlayer (HLS.js)
    ↓
请求 /api/video/{dramaName}/{filename}
    ↓
Express 视频流接口（Range 请求支持）
    ↓
D:\video_data\videos\{dramaName}\{filename}
```

### 拖动实现

依赖 HTTP Range 请求：

```
浏览器发送:  Range: bytes=1048576-2097152
服务端返回:  206 Partial Content
             Content-Range: bytes 1048576-2097152/52428800
```

---

## 六、服务端设计

采用 **Node.js + Express**，监听 `0.0.0.0:3001`（允许局域网访问）。

### 依赖

| 包       | 版本   | 用途         |
|---------|------|------------|
| express | 4.x  | HTTP 服务框架  |
| cors    | 2.x  | 跨域支持       |
| helmet  | 7.x  | 安全头        |
| lowdb   | 7.x  | JSON 文件数据库 |

### 启动流程

1. 初始化 lowdb，读取/创建 `database/drama.json`
2. 调用 `scanVideoDirectory()` — 扫描外部目录
3. 将扫描结果写入 dramas 和 episodes 表
4. `play_history` 表保留不动（持久化数据）
5. 启动 HTTP 服务

---

## 七、API 接口

| 接口                              | 方法   | 描述                |
|----------------------------------|------|-------------------|
| `/api/dramas`                    | GET  | 获取短剧列表（按创建时间倒序）  |
| `/api/dramas/:id`                | GET  | 获取单个短剧详情          |
| `/api/episodes/:dramaId`         | GET  | 获取指定短剧的剧集列表       |
| `/api/video/:dramaName/:filename` | GET  | 视频流（支持 Range 请求）  |
| `/covers/:filename`              | GET  | 封面图片              |
| `/api/history`                   | POST | 保存播放记录（upsert）    |
| `/api/history/:drama_id`         | GET  | 获取播放记录            |
| `/api/test/:dramaName/:filename` | GET  | 调试端点（文件存在性检查）     |

---

## 八、数据库设计

使用 **lowdb**（JSON 文件存储），数据文件位于 `server/database/drama.json`。

### 数据结构

```json
{
  "dramas": [
    {
      "id": 1,
      "title": "短剧名称",
      "description": "短剧描述",
      "cover_url": "封面文件名.png",
      "video_url": "短剧名/第一集.mp4",
      "episode_count": 12,
      "created_at": "2026-05-21T15:41:41.998Z"
    }
  ],
  "episodes": [
    {
      "id": 1,
      "drama_id": 1,
      "title": "第1集",
      "cover_url": "封面文件名.png",
      "video_url": "短剧名/第1集.mp4",
      "episode_number": 1
    }
  ],
  "play_history": [
    {
      "id": 1,
      "drama_id": 1,
      "episode_id": 3,
      "progress": 45.2,
      "updated_at": "2026-05-21T15:32:18.772Z"
    }
  ]
}
```

### 重要说明

- **dramas 和 episodes**：每次服务启动时由 `scanVideoDirectory()` 完全重建（非持久化）
- **play_history**：持久化保存，服务重启不丢失
- 启动扫描逻辑：遍历 `D:\\video_data\\videos\\` 下所有子目录 → 每个子目录 = 一部短剧 → 子目录内所有视频文件 = 剧集 → 在 `D:\\video_data\\pictures\\` 中按短剧名前缀匹配封面

---

## 九、视频资源管理

### 目录结构

```
D:\video_data\
├── videos\
│   ├── 北派寻宝笔记\
│   │   ├── 第63集.mp4
│   │   ├── 第64集.mp4
│   │   └── ...
│   ├── 天下第一纨绔\
│   │   ├── 第1集.mp4
│   │   └── ...
│   └── ...更多短剧\
└── pictures\
    ├── 北派寻宝笔记.png
    ├── 天下第一纨绔.png
    └── ...
```

### 扫描规则

1. **短剧识别**：`videos/` 下每个子目录 = 一部短剧
2. **剧集识别**：子目录内所有 `.mp4/.mkv/.webm/.mov/.m3u8` 文件，按文件名排序
3. **封面匹配**：在 `pictures/` 中查找以短剧名开头的 `.jpg/.jpeg/.png/.webp` 文件
4. **自动重建**：每次服务启动，dramas 和 episodes 表会被完全重建

### 支持的视频格式

`.mp4`, `.mkv`, `.webm`, `.mov`, `.m3u8`

---

## 十、局域网部署

### 服务端启动

```bash
cd server
npm start
# → Server running on http://0.0.0.0:3001
```

### 前端启动

```bash
cd client
npm run dev
# → http://localhost:5173
```

Vite 配置了代理：`/api` 和 `/covers` 请求转发到 `http://localhost:3001`。

### 局域网访问

```bash
# 获取本机 IP（Windows）
ipconfig | findstr IPv4
# 假设 IP: 192.168.1.10
```

其他设备访问：`http://192.168.1.10:5173`

---

## 十一、项目结构

```
project/
├── client/                          # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── VideoPlayer.tsx      # HLS.js 播放器（状态机 + 键盘控制）
│   │   │   └── DramaList.tsx        # 短剧列表（30s 自动轮询）
│   │   ├── pages/
│   │   │   └── PlayPage.tsx         # 播放页（剧集列表 + 进度保存）
│   │   ├── services/
│   │   │   └── api.ts              # Axios API 封装 + 类型定义
│   │   ├── App.tsx                  # 路由配置（/ 和 /play/:id）
│   │   ├── main.tsx                 # 入口（BrowserRouter）
│   │   └── index.css               # TailwindCSS + 暗色主题 CSS 变量
│   ├── index.html
│   ├── vite.config.ts               # Vite 配置 + API 代理
│   ├── tsconfig.json
│   └── package.json
│
├── server/                          # Express 后端
│   ├── database/
│   │   └── drama.json              # lowdb 数据文件（运行时生成）
│   ├── public/
│   │   └── covers/                  # 备用封面目录
│   ├── routes/                      # （预留）路由模块目录
│   ├── controllers/                 # （预留）控制器目录
│   ├── app.js                       # 主入口（API + 视频流 + 目录扫描）
│   └── package.json
│
├── .trae/
│   └── skills/                      # Agent Skills
│       ├── react/
│       ├── express/
│       ├── vite/
│       ├── short-drama-player/
│       └── short-drama-init/
│
├── framework.md                     # 本文件
├── README.md
└── LICENSE
```

---

## 十二、技术栈总结

### 前端

| 模块   | 技术             |
|------|----------------|
| 框架   | React 18       |
| 语言   | TypeScript     |
| 构建   | Vite 5         |
| UI   | TailwindCSS 3 + 自定义暗色主题 |
| 播放器  | HLS.js 1.4     |
| 路由   | React Router 6 |
| 请求   | Axios 1.6      |

### 后端

| 模块   | 技术         |
|------|------------|
| 服务框架 | Express 4  |
| 数据库  | lowdb 7 (JSON) |
| 安全   | helmet 7 + CORS |
| 视频流  | Node Stream + Range |

---

## 十三、开发阶段

| 阶段   | 内容                          | 状态    |
|------|------------------------------|-------|
| 第一阶段 | 短剧列表 + 视频播放 + 播放暂停 + 局域网访问  | ✅ 已完成 |
| 第二阶段 | HLS 流 + 播放记录 + 自动续播 + 剧集管理  | ✅ 已完成 |
| 第三阶段 | 用户系统 + 点赞收藏 + 推荐 + CDN + 云部署 | ⏳ 未开始 |

---

## 十四、后续扩展方向

- **HLS 转封装**：使用 FFmpeg 将 MP4 实时转封装为 HLS (m3u8+ts)，改善拖动体验
- **管理后台**：Web 界面上传视频、编辑短剧信息、管理封面
- **用户系统**：多用户播放历史、收藏、追剧
- **PWA**：Service Worker 缓存，离线播放
- **字幕支持**：WebVTT 字幕轨道
- **搜索**：短剧标题/描述关键词搜索
