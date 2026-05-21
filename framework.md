下面给出一个适合“短剧播放闭环项目”的完整技术方案，重点覆盖：

* Web 客户端
* 本地部署服务端
* 视频资源管理
* 播放能力
* 局域网测试
* 后续可扩展能力

整体方案默认：

* 单机本地部署
* 局域网内多人访问
* 短剧视频以 MP4/HLS 为主
* 不考虑复杂 DRM 与商业 CDN

---

# 一、整体项目架构

## 1. 系统整体结构

```text
┌─────────────────────┐
│      Web Client     │
│  (React/Vue 页面)   │
└─────────┬───────────┘
          │ HTTP/HTTPS
          │ REST API
          ▼
┌─────────────────────┐
│     Backend API     │
│  (Node.js / Python) │
└─────────┬───────────┘
          │
 ┌────────┴────────┐
 │                 │
 ▼                 ▼
Video Metadata   Video Files
(MySQL/SQLite)   (本地磁盘)
```

---

# 二、项目组件划分

推荐拆分为：

| 模块      | 职责               |
| ------- | ---------------- |
| Web 前端  | 短剧列表、播放页、播放器控制   |
| API 服务端 | 提供剧集数据、视频地址、播放记录 |
| 数据库     | 存储短剧元数据          |
| 文件存储    | 存放 MP4/HLS 视频    |
| 网络层     | 局域网访问            |

---

# 三、客户端（Web）设计

推荐技术：

| 技术    | 推荐                    |
| ----- | --------------------- |
| 前端框架  | React                 |
| UI 框架 | Ant Design / Tailwind |
| 视频播放器 | Video.js / HLS.js     |
| 状态管理  | Zustand / Redux       |
| 请求库   | Axios                 |

---

# 四、前端页面设计

---

## 1. 短剧列表页

### 功能

* 展示短剧封面
* 标题
* 简介
* 点击进入播放页

### 页面结构

```text
┌────────────────────┐
│ Header             │
├────────────────────┤
│ 短剧卡片 Grid       │
│ ┌────┐ ┌────┐      │
│ │封面│ │封面│      │
│ └────┘ └────┘      │
└────────────────────┘
```

---

## 2. 播放页

### 功能

* 视频播放
* 播放/暂停
* 拖动进度条
* 全屏
* 自动续播

### 页面结构

```text
┌────────────────────┐
│ Video Player       │
├────────────────────┤
│ 播放控制栏           │
│ ▶️ 进度条 音量 全屏  │
├────────────────────┤
│ 剧集信息             │
└────────────────────┘
```

---

# 五、播放器技术方案

推荐：

## 方案A（推荐）

# 使用 HLS.js

适合：

* 后续扩展直播
* 分片加载
* 更好的拖动体验
* 更适合长视频

架构：

```text
m3u8
 ├── ts1
 ├── ts2
 └── ...
```

---

## 方案B（简单）

# 直接 MP4 播放

```html
<video controls>
```

优点：

* 实现最快
* 无需转码

缺点：

* 拖动体验一般
* 大视频加载慢

---

# 六、服务端设计

推荐：

# Node.js + Express

原因：

* Web 项目开发效率高
* 前后端统一 JS
* 视频流支持成熟

---

# 七、服务端模块划分

---

## 1. API 层

提供：

| API            | 作用     |
| -------------- | ------ |
| GET /dramas    | 获取短剧列表 |
| GET /drama/:id | 获取剧详情  |
| GET /video/:id | 获取视频   |
| POST /history  | 保存播放记录 |

---

## 2. 视频流服务

### 核心能力

支持：

* Range 请求
* 分段加载
* 快进拖动

Node.js 示例：

```js
res.writeHead(206, {
  'Content-Range': ...
})
```

这是视频播放器流式播放的核心。

---

## 3. 数据库层

推荐：

| 方案     | 适用     |
| ------ | ------ |
| SQLite | 单机快速开发 |
| MySQL  | 后续扩展   |

---

# 八、数据库设计

---

## drama 表

| 字段          | 类型      |
| ----------- | ------- |
| id          | int     |
| title       | varchar |
| cover_url   | varchar |
| description | text    |
| video_url   | varchar |

---

## play_history 表

| 字段         | 类型       |
| ---------- | -------- |
| id         | int      |
| drama_id   | int      |
| progress   | int      |
| updated_at | datetime |

---

# 九、视频资源管理

推荐目录：

```text
server/
 ├── videos/
 │    ├── drama1.mp4
 │    └── drama2.mp4
 ├── covers/
 └── data/
```

---

# 十、局域网部署方案

---

## 1. 服务端启动

```bash
npm run start
```

监听：

```text
0.0.0.0:3000
```

不是：

```text
127.0.0.1
```

否则局域网无法访问。

---

## 2. 局域网访问

假设本机 IP：

```text
192.168.1.10
```

则其他设备访问：

```text
http://192.168.1.10:3000
```

---

# 十一、推荐项目结构

```text
project/
├── client/
│    ├── src/
│    ├── pages/
│    ├── components/
│    └── services/
│
├── server/
│    ├── routes/
│    ├── controllers/
│    ├── videos/
│    ├── database/
│    └── app.js
│
└── README.md
```

---

# 十二、推荐技术栈（最终建议）

---

## 前端

| 模块  | 技术           |
| --- | ------------ |
| 框架  | React        |
| UI  | TailwindCSS  |
| 播放器 | HLS.js       |
| 路由  | React Router |
| 请求  | Axios        |

---

## 后端

| 模块   | 技术          |
| ---- | ----------- |
| 服务框架 | Express     |
| 数据库  | SQLite      |
| ORM  | Prisma      |
| 视频流  | Node Stream |

---

# 十三、核心技术路径说明

---

## 1. 视频播放链路

```text
前端播放器
   ↓
请求 m3u8/mp4
   ↓
Node.js 视频流接口
   ↓
本地视频文件
```

---

## 2. 视频拖动实现

依赖：

```http
Range Request
```

浏览器：

```http
Range: bytes=1000-2000
```

服务端返回：

```http
206 Partial Content
```

---

## 3. HLS 转码（可选）

FFmpeg：

```bash
ffmpeg -i input.mp4 \
-hls_time 10 \
-hls_list_size 0 \
output.m3u8
```

---

# 十四、开发阶段建议

---

## 第一阶段（最小闭环）

实现：

* 短剧列表
* 视频播放
* 播放暂停
* 局域网访问

技术：

* React
* Express
* MP4

这是最快闭环。

---

## 第二阶段（增强）

增加：

* HLS
* 播放记录
* 自动续播
* 搜索

---

## 第三阶段（扩展）

增加：

* 用户系统
* 点赞收藏
* 推荐系统
* CDN
* 云部署

---

# 十五、推荐实施方案（最适合当前需求）

推荐你采用：

## 前端

```text
React + Tailwind + HLS.js
```

## 后端

```text
Node.js + Express
```

## 数据库

```text
SQLite
```

## 视频

```text
MP4（第一版）
后续升级 HLS
```

原因：

* 开发速度快
* 技术复杂度低
* 播放体验足够
* 易于本地部署
* 易于局域网测试
* 后续容易扩展

---

# 十六、最终架构图（推荐）

```text
                ┌────────────────┐
                │   Web Browser  │
                │ React + HLS.js │
                └───────┬────────┘
                        │
                 HTTP API / Video
                        │
                ┌───────▼────────┐
                │ Express Server │
                │                │
                │ REST API       │
                │ Video Stream   │
                └───────┬────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
         ▼                             ▼
   SQLite Database              Local Videos
```

## 视屏资源存放在本地路径

- D:\video_data