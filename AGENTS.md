# AGENTS.md — 短剧播放闭环项目

> 本文档面向 AI 编码助手。如果你对本项目一无所知，请先阅读本文档再动手修改代码。

---

## 项目概述

本项目是一个基于 **React + Express + lowdb + Redis** 的短剧视频播放平台，支持局域网部署和多人同时访问。核心特点是：

- 视频文件存放在外部目录（`D:\video_data`），服务端启动时自动扫描并建立索引。
- 前端使用 HLS.js + 原生 `<video>` 降级方案播放视频。
- **数据层采用 Redis + lowdb 混合架构**：Redis 作为缓存层（会话、视频缓存、高光点），lowdb（JSON 文件数据库）作为持久化存储。`dramas` 和 `episodes` 表在每次启动时由扫描逻辑全量重建，`play_history`、`users`、`highlights` 表持久化保存。
- Redis 不可用时自动降级到 lowdb，保证服务可用性。
- 当前处于第三阶段完成状态：短剧列表、视频播放、播放记录、自动续播、局域网访问、用户系统、高光点打标均已实现。

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
| 状态管理 | React Context | AuthContext 管理用户登录状态 |

### 后端 (`server/`)

| 模块 | 技术 | 说明 |
|------|------|------|
| 服务框架 | Express 4 | 监听 `0.0.0.0:3001`，允许局域网访问 |
| 主数据库 | lowdb 7 | JSON 文件 `database/drama.json`，启动时初始化 |
| **缓存层** | **ioredis** | **Redis 6+，支持自动重连和降级到 lowdb** |
| 认证 | JWT + bcrypt | 双 Token 机制（Access Token 2h，Refresh Token 30d） |
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
│   │   │   ├── DramaList.tsx        # 短剧列表，30 秒自动轮询
│   │   │   └── AuthModal.tsx        # 登录/注册弹窗
│   │   ├── pages/
│   │   │   └── PlayPage.tsx         # 播放页（剧集列表 + 进度保存 + Canvas 缩略图）
│   │   ├── context/
│   │   │   └── AuthContext.tsx      # 用户认证上下文
│   │   ├── services/
│   │   │   └── api.ts              # Axios 封装 + TypeScript 类型定义
│   │   ├── App.tsx                  # 路由配置
│   │   ├── main.tsx                 # 入口（StrictMode + BrowserRouter + AuthProvider）
│   │   └── index.css               # Tailwind 指令 + 暗色主题 CSS 变量 + 大量自定义样式
│   ├── index.html                   # lang="zh-CN"
│   ├── vite.config.ts               # Vite 配置 + API 代理
│   ├── tsconfig.json                # strict 模式，路径别名 `@/*` -> `src/*`
│   └── package.json
│
├── server/                          # Express 后端（CommonJS）
│   ├── app.js                       # 唯一主入口，~800 行，全部路由/逻辑都在此文件
│   ├── redis.js                     # Redis 客户端封装（带自动重连和降级）
│   ├── package.json
│   ├── .env                         # 环境变量配置（JWT_SECRET, REDIS_URL）
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

### 环境变量配置

在 `server/.env` 文件中配置：

```env
JWT_SECRET=your-strong-secret-key-here
REDIS_URL=redis://localhost:6379
PORT=3001
```

> **注意**：`JWT_SECRET` 为必填项，缺失会导致服务启动失败。`REDIS_URL` 可选，不配置则使用 lowdb 降级模式。

### 启动 Redis（可选）

```bash
# Linux/macOS
redis-server

# Windows（使用 WSL 或 Redis 官方 Windows 版本）
redis-server.exe
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

### Redis 缓存架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Redis 缓存层                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Sessions      │  │  Video Cache    │  │  Highlights     │ │
│  │  session:userid │  │  vcache:key     │  │  highlight:id   │ │
│  │  TTL: 30天      │  │  TTL: 10分钟    │  │  TTL: 1小时     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ▼ 降级
┌─────────────────────────────────────────────────────────────────┐
│                     lowdb (drama.json)                         │
│  dramas | episodes | play_history | episode_posters | users    │
│         | highlights | sessions (fallback)                     │
└─────────────────────────────────────────────────────────────────┘
```

### 启动流程

1. 加载 `.env` 环境变量，校验 `JWT_SECRET` 必填项。
2. **尝试连接 Redis**（自动重连 5 次，失败则降级到 lowdb）。
3. 初始化 lowdb，读取/创建 `server/database/drama.json`。
4. 调用 `scanVideoDirectory()` 扫描 `D:\video_data\videos\`：
   - 每个子目录 = 一部短剧（写入 `dramas` 表）。
   - 子目录内视频文件（`.mp4/.mkv/.webm/.mov/.m3u8`）按文件名排序 = 剧集（写入 `episodes` 表）。
   - 在 `pictures/` 中按**短剧名前缀**匹配封面（`.jpg/.jpeg/.png/.webp`）。
   - **`dramas` 和 `episodes` 表每次全量清空后重建**；`play_history`、`users`、`highlights` 保留不动。
5. 启动 HTTP 服务，之后每 30 秒自动重新扫描一次。

### 数据流

```
浏览器 (React)
  │ HTTP /api/*, /covers/*
  ▼
Vite dev server (5173) ──代理──▶ Express (3001)
  ▼
Redis (缓存层) ↔ lowdb (drama.json)          外部目录 D:\video_data\
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

### 公共接口

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
| `/api/cache/status` | GET | 缓存状态（Redis/lowdb 后端信息） |
| `/api/cache/clear` | POST | 清空视频缓存 |
| `/api/scan` | GET | 手动触发目录扫描 |
| `/api/test/:dramaName/:filename` | GET | **调试端点**，暴露文件系统路径信息 |

### 用户认证接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册（username, password, phone?） |
| `/api/auth/login` | POST | 用户登录（username, password） |
| `/api/auth/refresh` | POST | 刷新 Token（refreshToken） |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/user/profile` | GET | 获取用户信息（需登录） |
| `/api/user/profile` | PUT | 更新用户信息（nickname, avatar） |
| `/api/user/metadata` | GET | 获取用户元数据 |
| `/api/user/metadata` | PUT | 更新用户元数据 |

### 高光点接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/episodes/:episodeId/highlights` | GET | 获取剧集高光点（前端使用） |
| `/internal/highlights` | POST | 写入高光点（内部接口） |
| `/internal/highlights/:episodeId` | DELETE | 删除高光点（内部接口） |

### POST `/api/history` 输入校验规则

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
  ],
  "users": [
    {
      "id": 1,
      "username": "user1",
      "password": "$2b$10$...",
      "phone": "138****8888",
      "email": null,
      "avatar": null,
      "nickname": "用户1",
      "role": "user",
      "status": "active",
      "metadata": {
        "watch_count": 0,
        "favorite_count": 0,
        "last_login": null,
        "created_at": "...",
        "preferences": {}
      },
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "highlights": [
    {
      "episode_id": 1,
      "points": [25, 50, 75],
      "updated_at": "..."
    }
  ],
  "sessions": {}
}
```

---

## Redis 缓存键结构

| 前缀 | 格式 | TTL | 说明 |
|------|------|-----|------|
| `session:` | `session:{userId}` | 30天 | 用户会话（Access Token、Refresh Token、最后活跃时间） |
| `vcache:` | `vcache:{key}` | 10分钟 | 视频缓存（缓冲范围等） |
| `highlight:` | `highlight:{episodeId}` | 1小时 | 高光点数据缓存 |

---

## Redis 模块功能概述

`server/redis.js` 提供了完整的 Redis 客户端封装，具备以下特性：

### 核心功能

| 功能 | 说明 |
|------|------|
| **自动重连** | 最多重试 5 次，指数退避策略（200ms ~ 2000ms） |
| **优雅降级** | Redis 不可用时自动切换到 lowdb |
| **TTL 管理** | 自动设置过期时间，无需手动清理 |
| **优雅关闭** | 支持 `closeRedis()` 安全断开连接 |

### 会话管理（Session）

- **优先使用 Redis**：Session 数据存储在 Redis，30天 TTL 自动过期
- **降级到 lowdb**：Redis 不可用时，数据写入 `db.data.sessions` 对象
- **强制下线支持**：通过 `deleteSession(userId)` 可立即失效会话

### 视频缓存（Video Cache）

- **仅 Redis**：视频缓存只在 Redis 可用时生效
- **10分钟 TTL**：自动淘汰过期缓存
- **模式匹配删除**：支持按 pattern 批量清理

### 高光点缓存（Highlights）

- **双写策略**：先写 lowdb（持久化），再写 Redis（缓存）
- **1小时 TTL**：减少数据库读取压力
- **读取优先**：先查 Redis，未命中再查 lowdb

### Redis API 方法

| 方法 | 功能 |
|------|------|
| `connectRedis()` | 连接 Redis，返回连接成功/失败 |
| `closeRedis()` | 优雅关闭连接 |
| `isRedisReady()` | 检查 Redis 是否可用 |
| `getSession(userId)` | 获取用户会话 |
| `setSession(userId, data)` | 设置用户会话 |
| `deleteSession(userId)` | 删除用户会话 |
| `getVideoCache(key)` | 获取视频缓存 |
| `setVideoCache(key, data)` | 设置视频缓存 |
| `clearVideoCache(pattern)` | 清空视频缓存 |
| `getHighlights(episodeId)` | 获取高光点 |
| `setHighlights(episodeId, points)` | 设置高光点 |
| `getCacheStatus()` | 获取缓存状态（后端类型、键数量） |

### 环境变量配置

```env
# 必填项，用于 JWT 签名
JWT_SECRET=your-strong-secret-key-here

# 可选，Redis 连接地址，不配置则使用 lowdb 降级模式
REDIS_URL=redis://localhost:6379

# 可选，服务端口，默认 3001
PORT=3001
```

### 降级机制说明

1. **启动时**：尝试连接 Redis，失败则记录警告并使用 lowdb
2. **运行时**：Redis 断开后自动切换到 lowdb，重连成功后恢复
3. **Session**：lowdb 模式下使用 `db.data.sessions` 对象，需定期清理过期会话
4. **视频缓存**：lowdb 模式下跳过缓存，直接读取文件
5. **高光点**：lowdb 模式下直接读取 `db.data.highlights`