# 短剧播放平台 - 项目优化清单

> 创建时间: 2026-05-21
> 优先级: P0 (立即修复) > P1 (架构债务) > P2 (代码质量) > P3 (工程化完善)

---

## P0 · 立即修复（Bug / 安全隐患）

### #1 POST 端点无输入校验 ✅
- **位置**: `server/app.js` — POST `/api/history`
- **风险**: 恶意请求可写入任意数据，导致 JSON 损坏或服务崩溃
- **解决路径**: 在路由中添加校验中间件：`{drama_id: number, episode_id: number, progress: number}`，用 `typeof` 或 `joi/zod` 校验
- **状态**: ✅ 已完成
- **完成时间**: 2026-05-21
- **修改内容**:
  - 添加了 drama_id、episode_id、progress 的类型和范围校验
  - 使用 Number.isInteger() 确保是整数
  - progress 限制在 0-86400 范围内

### #2 无优雅关闭 ✅
- **位置**: `server/app.js` — 末尾
- **风险**: Ctrl+C 或进程 kill 时正在写入的 play_history 数据丢失
- **解决路径**: 监听 `SIGINT/SIGTERM`，调用 `await db.write()` 后再 `process.exit(0)`
- **状态**: ✅ 已完成
- **完成时间**: 2026-05-21
- **修改内容**:
  - 添加了 gracefulShutdown 函数
  - 监听 SIGINT 和 SIGTERM 信号
  - 保存数据库后再退出
  - 添加30秒超时强制退出机制

### #3 Mock 剧集共用同一个 video_url ✅
- **位置**: `client/src/pages/PlayPage.tsx` — `createMockEpisodes()`
- **风险**: 所有集播放同一视频，用户体验差
- **解决路径**: 如果 episodes 表为空，应从 drama 的 video_url 推导第1集，其余集标记为"即将上线"或直接隐藏
- **状态**: ✅ 已完成
- **完成时间**: 2026-05-21
- **修改内容**:
  - 从 drama.video_url 中提取目录路径
  - 自动识别起始集数（从"第63集"等文件名提取）
  - 每集生成独立的 video_url
  - 格式：`{baseDir}第{集数}集.mp4`

---

## P1 · 架构债务（高优先级）

### #4 单体服务文件
- **位置**: `server/app.js` — 全部路由/逻辑在 350+ 行的单文件中
- **影响**: 难以维护，routes/ 和 controllers/ 目录空置浪费
- **解决路径**: 拆分为：`routes/dramas.js`、`routes/episodes.js`、`routes/video.js`、`routes/history.js`，每个路由文件只做路由分发，逻辑放入 controllers/
- **状态**: ⬜ 待处理

### #5 外部目录路径硬编码
- **位置**: `server/app.js` — `const externalBaseDir = 'D:\\video_data'`
- **影响**: 换机器/换盘符即不可用，无跨平台兼容性
- **解决路径**: 改为 `process.env.VIDEO_DATA_DIR` 或 `path.join(__dirname, 'videos')`，创建 `.env.example`
- **状态**: ⬜ 待处理

### #6 scanVideoDirectory 每次全量重建
- **位置**: `server/app.js` — `db.data.dramas = []` 清空后重建
- **影响**: 任何运行时对 dramas/episodes 的手动修改会在重启后丢失
- **解决路径**: 改为增量扫描：只添加新目录/新文件，不删除已有数据；或明确文档说明"dramas 表由目录驱动，不可手动编辑"
- **状态**: ⬜ 待处理

### #7 无速率限制
- **位置**: `server/app.js` — 全局
- **影响**: 局域网内多设备同时访问或恶意轮询可能导致服务过载
- **解决路径**: 安装 `express-rate-limit`，对 `/api/` 路由设置 100 req/min 限制
- **状态**: ⬜ 待处理

### #8 调试端点暴露 ✅
- **位置**: `server/app.js` — `GET /api/test/:dramaName/:filename`
- **影响**: 暴露文件系统路径信息，安全风险
- **解决路径**: 用 `if (process.env.NODE_ENV !== 'production')` 包裹，或直接删除（调试用途可临时加回）
- **状态**: ✅ 已完成
- **完成时间**: 2026-06-04
- **修改内容**:
  - 用 `if (process.env.NODE_ENV !== 'production')` 包裹整个路由
  - 移除了 JSON 响应中的 `fullPath` 字段（不再泄露文件路径）
  - 合并了 4 条 console.log 为 1 条结构化日志

---

## P2 · 代码质量（中优先级）

### #9 VideoPlayer 组件过大
- **位置**: `client/src/components/VideoPlayer.tsx` — 600 行、7 个 useState、15 个 useCallback
- **影响**: 难以测试和复用，状态逻辑混杂
- **解决路径**: 拆分为：
  1. `useVideoPlayer` hook（状态机核心）
  2. `useKeyboardShortcuts` hook
  3. `VideoControls` 子组件（进度条/音量/全屏按钮）
  4. `VideoPlayer` 只做组装
- **状态**: ⬜ 待处理

### #10 Episode ID 生成 O(n)
- **位置**: `server/app.js` — `Math.max(...db.data.episodes.map(e => e.id)) + 1`
- **影响**: 集数多时每次插入都遍历全数组
- **解决路径**: 维护一个自增计数器：`let nextEpisodeId = db.data.episodes.length > 0 ? Math.max(...ids) + 1 : 1`（只在扫描开始时算一次）
- **状态**: ⬜ 待处理

### #11 封面匹配仅用前缀
- **位置**: `server/app.js` — `f.toLowerCase().startsWith(dramaName.toLowerCase())`
- **影响**: 短剧名"天下"会匹配到"天下第一纨绔.png"和"天下无双.png"
- **解决路径**: 改为精确匹配文件名去扩展名后是否等于短剧名，或约定封面命名规则为 `{剧名}.cover.{ext}`
- **状态**: ⬜ 待处理

### #12 无 React Error Boundary
- **位置**: `client/src/` — 全局
- **影响**: 播放器崩溃会导致整个页面白屏
- **解决路径**: 添加 ErrorBoundary 组件包裹 `<Routes>`，播放器错误时显示"播放失败，请刷新"而非白屏
- **状态**: ⬜ 待处理

### #13 30 秒轮询间隔硬编码
- **位置**: `client/src/components/DramaList.tsx` — `setInterval(..., 30000)`
- **影响**: 无法根据场景调整（局域网可更短，外网需更长）
- **解决路径**: 提取为组件 prop 或环境变量 `VITE_POLL_INTERVAL`，默认 30000
- **状态**: ⬜ 待处理

---

## P3 · 工程化完善（低优先级）

### #14 零测试覆盖
- **位置**: 全局
- **影响**: 无法保证重构不引入回归
- **解决路径**: 优先加：
  1. server/ API 集成测试（supertest + jest）
  2. VideoPlayer 组件测试（React Testing Library）
- **状态**: ⬜ 待处理

### #15 无 ESLint / Prettier 配置
- **位置**: 全局
- **影响**: 代码风格不统一，潜在 bug 无法静态捕获
- **解决路径**: 安装 `eslint` + `@typescript-eslint` + `prettier`，添加 `.eslintrc.js` 和 `.prettierrc`，husky pre-commit hook
- **状态**: ⬜ 待处理

### #16 TailwindCSS 版本混合
- **位置**: `client/package.json` — `tailwindcss: ^3.4.1` + `@tailwindcss/vite: ^4.0.13`
- **影响**: v3 的核心 + v4 的 Vite 插件可能导致构建行为不一致
- **解决路径**: 统一到 v4：`tailwindcss: ^4.0` + `@tailwindcss/vite: ^4.0`，或全部降回 v3
- **状态**: ⬜ 待处理

### #17 无环境变量文件
- **位置**: 项目根 — 无 `.env` / `.env.example`
- **影响**: 新开发者不知道需要配置什么
- **解决路径**: 创建 `.env.example`：
  ```bash
  VIDEO_DATA_DIR=D:\\video_data
  PORT=3001
  NODE_ENV=development
  ```
- **状态**: ⬜ 待处理

### #18 后端无 TypeScript
- **位置**: `server/` — 全部 `.js` 文件
- **影响**: 接口变更时无类型检查，前端 TS 类型定义与后端脱节
- **解决路径**: 渐进迁移：先加 `jsconfig.json` + JSDoc 类型注释，后续用 ts-node 或直接改 `.ts`
- **状态**: ⬜ 待处理

### #19 无加载骨架屏
- **位置**: `client/src/components/DramaList.tsx` — 只有"正在获取剧集数据..."文字
- **影响**: 加载体验差，尤其局域网环境下首次加载较慢
- **解决路径**: TailwindCSS `animate-pulse` 实现卡片骨架屏（灰色块模拟封面+标题+描述）
- **状态**: ⬜ 待处理

### #20 空目录残留
- **位置**: `server/routes/`、`server/controllers/` — 空目录
- **影响**: 误导开发者以为代码已模块化
- **解决路径**: P1#4 解决后自然填充；在此之前添加 `.gitkeep` 并注释说明"待拆分"
- **状态**: ⬜ 待处理

---

## 完成进度

| 优先级 | 总数 | 已完成 | 待处理 |
|--------|------|--------|--------|
| P0 | 3 | 3 | 0 |
| P1 | 5 | 1 | 4 |
| P2 | 5 | 0 | 5 |
| P3 | 7 | 0 | 7 |
| **总计** | **20** | **4** | **16** |

---

## 下一步行动

### 立即执行（P0）
1. ✅ 已有后端测试脚本（`test-video-flow.js`），可验证后端功能
2. ✅ 添加输入校验中间件
3. ✅ 实现优雅关闭
4. ✅ 修复Mock剧集video_url问题

### 建议按顺序执行
```
P1 (#4-#8) → P2 (#9-#13) → P3 (#14-#20)
```

---

## 已完成项目详情

### P0 (2026-05-21)

#### #1 POST 端点无输入校验
- **修改文件**: `server/app.js`
- **技术细节**:
  - drama_id: 正整数校验
  - episode_id: 正整数校验
  - progress: 0-86400 范围校验

#### #2 无优雅关闭
- **修改文件**: `server/app.js`
- **技术细节**:
  - gracefulShutdown 函数
  - SIGINT/SIGTERM 信号监听
  - 30秒超时保护

#### #3 Mock剧集video_url重复
- **修改文件**: `client/src/pages/PlayPage.tsx`
- **技术细节**:
  - 动态提取起始集数
  - 每集独立video_url
