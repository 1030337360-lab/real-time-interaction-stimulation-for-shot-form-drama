# AGENTS.md — 短剧播放闭环项目

> 本文档面向 AI 编码助手。如果你对本项目一无所知，请先阅读本文档再动手修改代码。

---

## 项目概述

本项目是一个基于 **React + Express + lowdb** 的短剧视频播放平台，支持局域网部署和多人同时访问。核心特点是：

- 视频文件存放在外部目录（`D:\video_data`），服务端启动时自动扫描并建立索引。
- 前端使用 HLS.js + 原生 `<video>` 降级方案播放视频。
- 数据层使用 lowdb（JSON 文件数据库），`dramas` 和 `episodes` 表在每次启动时由扫描逻辑全量重建，`play_history` 表持久化保存。
- 当前处于第二阶段完成状态：短剧列表、视频播放、播放记录、自动续播、局域网访问均已实现。

---

## 技术栈

### 前端 (`client/`)

| 模块 | 技术 | 说明 |
|------|------|------|
| 框架 | React 18 | 函数组件 + Hooks |
| 语言 | TypeScript 5.3 | `strict: true`，启用 `noUnusedLocals` / `noUnusedParameters` |
| 构建工具 | Vite 5 | 开发服务器端口 5173，代理 `/api` 和 `/covers` 到后端 |
| UI 样式 | TailwindCSS 3 + `@tailwindcss/vite` 4.x | **注意：版本混合**，自定义暗色主题 CSS 变量 |
| 视频播放 | HLS.js 1.4 | 支持 m3u8，不支持时降级到原生 video |
| 路由 | React Router 6 | 两个路由：`/` 列表页，`/play/:id` 播放页 |
| HTTP 请求 | Axios 1.6 | `baseURL: '/api'`，超时 10 秒 |

### 后端 (`server/`)

| 模块 | 技术 | 说明 |
|------|------|------|
| 服务框架 | Express 4 | 监听 `0.0.0.0:3001`，允许局域网访问 |
| 数据库 | lowdb 7 | JSON 文件 `database/drama.json`，启动时初始化 |
| 安全 | helmet 7 + CORS | 基础安全头，全局跨域允许 |
| 视频流 | Node.js Stream + Range 请求 | 支持拖动跳转（206 Partial Content） |
| 进程管理 | nodemon | 开发模式热重载 |

---

## 项目结构

```
project/
├── client/                          # React 前端（ESM）
│   ├── src/
│   │   ├── components/
│   │   │   ├── VideoPlayer.tsx      # HLS.js 播放器，~640 行，8 状态状态机
│   │   │   └── DramaList.tsx        # 短剧列表，30 秒自动轮询
│   │   ├── pages/
│   │   │   └── PlayPage.tsx         # 播放页（剧集列表 + 进度保存 + Canvas 缩略图）
│   │   ├── services/
│   │   │   └── api.ts              # Axios 封装 + TypeScript 类型定义
│   │   ├── App.tsx                  # 路由配置
│   │   ├── main.tsx                 # 入口（StrictMode + BrowserRouter）
│   │   └── index.css               # Tailwind 指令 + 暗色主题 CSS 变量 + 大量自定义样式
│   ├── index.html                   # lang="zh-CN"
│   ├── vite.config.ts               # Vite 配置 + API 代理
│   ├── tsconfig.json                # strict 模式，路径别名 `@/*` -> `src/*`
│   └── package.json
│
├── server/                          # Express 后端（CommonJS）
│   ├── app.js                       # 唯一主入口，~570 行，全部路由/逻辑都在此文件
│   ├── package.json
│   ├── database/
│   │   └── drama.json              # lowdb 数据文件（运行时生成，已入 .gitignore）
│   ├── public/covers/               # 备用封面目录
│   ├── routes/                      # 预留空目录（待拆分）
│   ├── controllers/                 # 预留空目录（待拆分）
│   ├── videos/                      # 本地视频存放目录（当前未使用）
│   └── covers/                      # 本地封面存放目录（当前未使用）
│
├── .trae/skills/                    # 项目内 Agent Skills（react / express / vite / short-drama-*）
├── test-video-flow.js               # 后端 API 流程测试脚本（需先启动后端）
├── framework.md                     # 详细技术框架文档（含表结构、状态机、部署说明）
├── TODOS.md                         # 项目优化清单（P0~P3，已完成 3/20）
├── README.md                        # 面向人类开发者的一页 README
└── package.json                     # 根目录空壳，仅含 axios 依赖，无实际脚本
```

---

## 构建与运行命令

### 安装依赖

```bash
# 前端
cd client && npm install

# 后端
cd server && npm install
```

### 开发模式（需要两个终端）

```bash
# 终端 1：启动后端
cd server
npm start            # node app.js，监听 0.0.0.0:3001
# 或 npm run dev     # nodemon 热重载

# 终端 2：启动前端
cd client
npm run dev          # vite，端口 5173
```

### 构建生产包

```bash
cd client
npm run build        # tsc && vite build
npm run preview      # vite preview
```

### 测试

```bash
# 后端功能测试（需后端已启动在 localhost:3001）
node test-video-flow.js
```

> 注意：前端目前**没有任何单元测试或集成测试**。

---

## 运行时架构

### 视频资源目录结构（外部硬编码路径）

```
D:\video_data\
├── videos\                          # 视频文件
│   ├── 北派寻宝笔记\
│   │   ├── 第63集.mp4
│   │   ├── 第64集.mp4
│   │   └── ...
│   └── ...更多短剧目录\
└── pictures\                        # 封面图片
    ├── 北派寻宝笔记.png
    └── ...
```

### 启动流程

1. 初始化 lowdb，读取/创建 `server/database/drama.json`。
2. 调用 `scanVideoDirectory()` 扫描 `D:\video_data\videos\`：
   - 每个子目录 = 一部短剧（写入 `dramas` 表）。
   - 子目录内视频文件（`.mp4/.mkv/.webm/.mov/.m3u8`）按文件名排序 = 剧集（写入 `episodes` 表）。
   - 在 `pictures/` 中按**短剧名前缀**匹配封面（`.jpg/.jpeg/.png/.webp`）。
   - **`dramas` 和 `episodes` 表每次全量清空后重建**；`play_history` 保留不动。
3. 启动 HTTP 服务，之后每 30 秒自动重新扫描一次。

### 数据流

```
浏览器 (React)
  │ HTTP /api/*, /covers/*
  ▼
Vite dev server (5173) ──代理──▶ Express (3001)
  ▼
lowdb (drama.json)          外部目录 D:\video_data\
```

### 播放链路

```
前端 VideoPlayer
  │ 请求 /api/video/{dramaName}/{filename}?maxBuffer=...&current=...
  ▼
Express streamVideo()（支持 Range 请求）
  ▼
D:\video_data\videos\{dramaName}\{filename}
```

---

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/dramas` | GET | 短剧列表（按创建时间倒序） |
| `/api/dramas/:id` | GET | 单个短剧详情 |
| `/api/episodes/:dramaId` | GET | 指定短剧的剧集列表（空时返回 mock 数据） |
| `/api/episodes/:episodeId/poster` | POST | 保存剧集缩略图（base64 JPEG） |
| `/api/video/:dramaName/:filename` | GET | 视频流（支持 `Range` 请求，查询参数 `maxBuffer`/`current`） |
| `/api/video/:filename` | GET | 视频流（旧版，仅本地目录） |
| `/covers/:filename` | GET | 封面图片（先查外部目录，再查本地，再查 public） |
| `/api/history` | POST | 保存/更新播放记录（body: `{drama_id, episode_id, progress}`） |
| `/api/history/:drama_id` | GET | 获取某短剧的播放记录 |
| `/api/cache/status` | GET | 视频缓存状态 |
| `/api/cache/clear` | POST | 清空视频缓存 |
| `/api/scan` | GET | 手动触发目录扫描 |
| `/api/test/:dramaName/:filename` | GET | **调试端点**，暴露文件系统路径信息 |

### POST `/api/history` 输入校验规则（P0 已修复）

- `drama_id`: 正整数 (`Number.isInteger` && > 0)
- `episode_id`: 正整数 (`Number.isInteger` && > 0)
- `progress`: 数字，范围 0 ~ 86400（最多 24 小时）

---

## 数据库表结构（lowdb JSON）

```json
{
  "dramas": [
    {
      "id": 1,
      "title": "短剧名称",
      "description": "短剧《短剧名称》",
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
  ],
  "episode_posters": [
    {
      "episode_id": 1,
      "poster": "data:image/jpeg;base64,...",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

---

## 代码风格与约定

### 语言与注释
- 项目内文档、TODO、代码注释、UI 文案**主要使用中文**。
- 日志输出也使用中文（如 `"加载视频中..."`、`"缓冲中..."`）。

### 前端规范
- **ESM**：`client/package.json` 设置 `"type": "module"`。
- **TypeScript 严格模式**：`strict: true`，不允许未使用的变量和参数。
- **路径别名**：`@/*` 映射到 `src/*`（仅在 `tsconfig.json` 中配置，Vite 未额外配 alias）。
- **组件导出**：使用命名导出（`export function ComponentName`）。
- **样式方案**：Tailwind 工具类 + 自定义 CSS 变量（暗色主题）+ 大量自定义 class（写在 `index.css`）。
  - CSS 变量前缀：`--bg-*`、`--text-*`、`--accent-*`、`--border-*`、`--shadow-*`、`--transition-*`、`--spacing-*`。
  - 移动端优先，最小触控目标 `44px`（`--touch-target`）。

### 后端规范
- **CommonJS**：`server/app.js` 使用 `require()`。
- **单文件架构**：目前所有路由、控制器、数据库初始化、视频流逻辑都在 `app.js` 一个文件中（约 570 行）。`routes/` 和 `controllers/` 目录为空，是已知架构债务。
- **错误处理**：普遍使用 `try/catch` + `res.status(500).json({ error: err.message })` 模式。

### 环境相关
- **后端端口**：`process.env.PORT || 3001`
- **前端开发端口**：5173（硬编码在 `vite.config.ts`）
- **外部目录硬编码**：`server/app.js` 第 36 行 `const externalBaseDir = 'D:\\video_data'`
- **无 `.env` 文件**：所有配置要么硬编码，要么依赖 `process.env.PORT`。

---

## 测试策略

当前测试覆盖极弱：

- **前端**：无任何测试框架、零测试用例。
- **后端**：`test-video-flow.js` 是一个 Node.js 脚本，使用 axios 对 localhost:3001 做端到端流程验证（获取列表 → 获取详情 → 获取剧集 → 构建视频 URL → HEAD 视频流 → 检查本地文件 → 封面请求 → 海报保存 → 进度保存/获取 → 缓存状态）。
  - 运行前**必须先启动后端服务**。
  - 该脚本硬编码了 `D:\video_data\videos` 路径用于文件存在性检查。

若要新增测试，优先方向（来自 `TODOS.md`）：
1. 后端 API 集成测试（supertest + jest）。
2. `VideoPlayer` 组件测试（React Testing Library）。

---

## 安全注意事项

- **helmet 和 CORS 已启用**，但 CORS 是全局允许（开发友好，生产需注意）。
- **POST 输入校验已加**：`/api/history` 有 `drama_id`/`episode_id`/`progress` 的类型和范围校验（2026-05-21 修复）。
- **调试端点暴露**：`GET /api/test/:dramaName/:filename` 会返回完整文件系统路径和存在性信息，存在信息泄露风险。生产环境应移除或加环境变量保护。
- **无速率限制**：局域网内多设备同时访问或恶意轮询可能导致服务过载。
- **优雅关闭已加**：监听 `SIGINT`/`SIGTERM`，先保存数据库再退出，30 秒超时强制退出（2026-05-21 修复）。
- **视频流接口**：未做身份验证和授权，任何人知道 URL 即可访问。
- **外部目录遍历**：视频接口使用 `path.join` 拼接路径，但参数来自 URL，需注意路径遍历风险（目前依赖 URL 编码和 Express 路由分段天然限制）。

---

## 已知问题与重点 TODO

详细清单见 `TODOS.md`，以下为对编码助手最关键的几项：

1. **单体服务文件**（P1）：`server/app.js` 350+ 行，所有逻辑在一个文件。`routes/` 和 `controllers/` 为空目录，需要拆分。
2. **外部路径硬编码**（P1）：`D:\video_data` 写死在代码中，换机器即失效。应改为环境变量配置。
3. **全量重建扫描**（P1）：每次启动/每 30 秒都会清空 `dramas` 和 `episodes` 后重建，手动修改会丢失。
4. **TailwindCSS 版本混合**（P3）：`tailwindcss: ^3.4.1` 与 `@tailwindcss/vite: ^4.0.13` 混用，可能导致构建行为不一致。
5. **VideoPlayer 过大**（P2）：`VideoPlayer.tsx` 约 640 行、15 个 `useCallback`、多个 `useEffect`，建议拆分为自定义 hooks + 子组件。
6. **零测试覆盖**（P3）：前后端均无单元测试。
7. **后端无 TypeScript**（P3）：`server/` 下全为 `.js` 文件，建议渐进迁移（先 JSDoc，再 ts-node）。
8. **无 ESLint / Prettier**（P3）：代码风格依赖人工一致。
9. **无环境变量文件**（P3）：没有 `.env.example`，新开发者不知道要配什么。
10. **封面匹配仅用前缀**（P2）：`startsWith(dramaName)` 会导致"天下"同时匹配"天下第一纨绔"和"天下无双"。

---

## 对 AI 助手的操作提示

- **修改后端时**：注意 `app.js` 是单文件，新增路由请放在合适的位置（通常按 `GET` → `POST` 分组），并确保 `db.read()` / `db.write()` 成对出现。
- **修改前端时**：注意 `index.css` 中已经存在大量与组件同名的自定义 class（如 `.video-player-container`、`.drama-card`），优先复用这些 class，而不是新增 Tailwind 原子类。
- **添加新接口时**：请在 `client/src/services/api.ts` 中同步添加类型定义和请求函数，保持前后端类型一致。
- **处理视频路径时**：中文文件名必须使用 `encodeURIComponent`；服务端接口参数解码由 Express 自动处理，但拼接 `path.join` 时仍需注意跨平台路径分隔符。
- **数据库操作**：lowdb 是异步读写 JSON 文件，每次写操作后记得 `await db.write()`。
- **不要假设存在测试**：修改后请手动验证，不要依赖自动化测试捕获回归。
