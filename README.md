# 短剧播放闭环项目

基于 React + Express + LowDB 的短剧视频播放平台，支持局域网部署和多人访问。

## 技术栈

### 前端
- React 18
- TypeScript
- Vite
- TailwindCSS
- HLS.js
- React Router

### 后端
- Node.js
- Express
- LowDB (JSON 数据库)
- CORS
- Helmet

## 项目结构

```
short-drama-project/
├── client/                    # 前端 React 应用
│   ├── src/
│   │   ├── components/       # 组件
│   │   │   ├── VideoPlayer.tsx
│   │   │   └── DramaList.tsx
│   │   ├── pages/            # 页面
│   │   │   └── PlayPage.tsx
│   │   ├── services/         # API 服务
│   │   │   └── api.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── server/                    # 后端 Express 服务
│   ├── database/             # JSON 数据库
│   │   └── drama.json
│   ├── public/               # 静态资源
│   ├── videos/               # 视频文件存储
│   ├── covers/               # 封面图片
│   ├── app.js
│   └── package.json
│
├── .trae/
│   └── skills/               # Agent Skills
│       ├── react/
│       ├── express/
│       ├── vite/
│       ├── short-drama-player/
│       └── short-drama-init/
│
└── README.md
```

## 功能特性

- 🎬 短剧列表展示
- 🎮 视频播放控制（播放/暂停、进度条、音量、全屏）
- 📋 播放列表管理
- 🔄 自动续播下一集
- 💾 播放进度自动保存
- ⭐ **高光点打标功能** - 在进度条上标记精彩片段
- 🎚️ **垂直音量滑块** - B站风格的音量控制
- 📱 响应式设计
- 🌐 局域网访问支持

## 快速开始

### 安装依赖

```bash
# 安装前端依赖
cd client
npm install

# 安装后端依赖
cd ../server
npm install
```

### 启动服务

```bash
# 启动后端服务（终端1）
cd server
npm start

# 启动前端开发服务器（终端2）
cd client
npm run dev
```

### 访问地址

- 前端：http://localhost:5173
- 后端 API：http://localhost:3001

### 局域网访问

1. 获取本机 IP 地址：
   ```bash
   # Windows
   ipconfig | findstr IPv4
   
   # Linux/Mac
   ifconfig | grep inet
   ```

2. 其他设备访问：`http://<你的IP>:5173`

## API 接口

### 公开接口（前端使用）

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/dramas` | GET | 获取短剧列表 |
| `/api/dramas/:id` | GET | 获取单个短剧 |
| `/api/episodes/:dramaId` | GET | 获取剧集列表 |
| `/api/episodes/:episodeId/highlights` | GET | 获取剧集高光点 |
| `/api/video/:filename` | GET | 视频流 |
| `/api/video/:dramaName/:filename` | GET | 带目录的视频流 |
| `/covers/:filename` | GET | 封面图片 |
| `/api/history` | POST | 保存播放记录 |
| `/api/history/:drama_id` | GET | 获取播放记录 |
| `/api/scan` | GET | 重新扫描视频目录 |

### 内部接口（其他进程使用）

| 接口 | 方法 | 描述 |
|------|------|------|
| `/internal/highlights` | POST | 写入高光点数据 |
| `/internal/highlights/:episodeId` | DELETE | 删除高光点数据 |

## 高光点打标功能

### 写入高光点

```bash
curl -X POST http://localhost:3001/internal/highlights \
  -H "Content-Type: application/json" \
  -d '{"episode_id": 1, "points": [25, 50, 75]}'
```

**参数说明：**
- `episode_id`: 剧集ID
- `points`: 高光点数组，值为 0-100 的百分比

### 获取高光点

```bash
curl http://localhost:3001/api/episodes/1/highlights
# 返回: [25, 50, 75]
```

## 视频文件说明

将视频文件放入外部目录 `D:\video_data\videos\`，每个短剧创建一个子目录。封面图片放入 `D:\video_data\pictures\`。

目录结构示例：
```
D:\video_data\
├── videos/
│   ├── 短剧名称1/
│   │   ├── 第1集.mp4
│   │   ├── 第2集.mp4
│   │   └── 第3集.mp4
│   └── 短剧名称2/
│       └── 第1集.mp4
└── pictures/
    ├── 短剧名称1.jpg
    └── 短剧名称2.jpg
```

## 数据库

使用 LowDB (JSON 文件)，数据文件位于 `server/database/drama.json`。

### 数据结构

```json
{
  "dramas": [],          // 短剧信息
  "episodes": [],        // 剧集信息
  "play_history": [],    // 播放记录
  "episode_posters": [], // 剧集海报
  "highlights": []       // 高光点数据
}
```

### highlights 数据格式

```json
{
  "episode_id": 1,
  "points": [25, 50, 75],
  "created_at": "2024-01-01T00:00:00.000Z",
  "updated_at": "2024-01-01T00:00:00.000Z"
}
```

## 播放器特性

### B站风格 UI
- 底部半透明渐变控制栏
- 细进度条，hover 时变粗
- 粉色 (#ff4757) 进度条配色
- 垂直音量滑块
- 环形加载动画
- 大号中央播放按钮

### 高光点显示
- 进度条上的红色实心圆点标记
- hover 时圆点放大效果
- 切换剧集自动更新高光点

## License

Apache License 2.0
<!-- git add
git commit -m "首次提交"

git pull origin main --allow-unrelated-histories
git push -u origin main

git push -->