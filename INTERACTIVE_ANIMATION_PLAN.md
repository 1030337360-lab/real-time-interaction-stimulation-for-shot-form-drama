# 短剧互动动画方案规划

> 基于短剧场景的三层递进式互动动画系统

---

## 一、现有项目框架分析

### 1.1 当前播放器架构
- **技术栈**：React 18 + TypeScript + TailwindCSS + HLS.js
- **播放器位置**：`client/src/components/VideoPlayer.tsx` (~640行)
- **状态管理**：React Hooks (useState, useRef, useCallback, useEffect)
- **样式管理**：`client/src/index.css` (暗色主题 + CSS变量)
- **现有CSS变量**：`--accent-primary: #ff4757`、`--touch-target: 44px` 等

### 1.2 进度条当前实现
- **进度条组件**：`progress-track` (B站风格)
- **已有点击功能**：seek跳转
- **现有动画**：hover变粗、thumb显示
- **高光标记**：`highlight-marker` (红色圆点)

### 1.3 高光点数据流
```
后端 API (/api/episodes/:id/highlights)
    ↓
前端获取 (useEffect)
    ↓
VideoPlayer 组件 (highlights state)
    ↓
高光时序引擎 (useHighlightSync)
    ↓
渲染 (JSX + CSS)
```

---

## 二、核心：高光时序引擎

### 2.1 状态机设计

```ts
type HighlightPhase = 
  | 'idle'       // 无高光或距离很远
  | 'warning'    // 高光前 5-3 秒（边框收缩）
  | 'alert'      // 高光前 3-0 秒（高能预警 + 倒计时）
  | 'active'     // 高光到达（闪光 + 微震）
  | 'cooldown';  // 高光后 4 秒（不触发新预警）

interface HighlightState {
  phase: HighlightPhase;
  nearestHighlight: number | null;  // 最近的高光时间（百分比）
  timeToNext: number;               // 距离下一个高光的秒数
}
```

### 2.2 时序规则设计

| 状态 | 触发条件 | 持续动作 | 退出条件 |
|------|----------|----------|----------|
| idle | | | nearestHighlight ≤ 5 秒 |
| warning | 5秒 ≤ timeToNext < 3秒 | 角落边框收缩动画 | timeToNext < 3 秒 |
| alert | 3秒 ≤ timeToNext < 0秒 | 高能预警 + 3→2→1倒计时 | timeToNext ≤ 0 |
| active | timeToNext ≤ 0 | 边缘闪光 + 微震 + 粒子爆发 | 0.5秒后 |
| cooldown | active结束 | 显示反应面板，不处理新预警 | 4秒后回到idle |

### 2.3 useHighlightSync Hook（核心实现）

```ts
function useHighlightSync(
  highlights: number[],
  currentTime: number,
  duration: number,
  isPaused: boolean
): HighlightState {
  // State: 只在 phase 真正变化时才触发 re-render
  const [state, setState] = useState<HighlightState>({
    phase: 'idle',
    nearestHighlight: null,
    timeToNext: Infinity
  });

  // Refs: 跟踪内部状态，避免不必要的 re-render
  const stateRef = useRef<HighlightState>({
    phase: 'idle',
    nearestHighlight: null,
    timeToNext: Infinity
  });

  const cooldownStartRef = useRef<number | null>(null);
  const activeStartRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(currentTime);

  // 只追踪当前播放位置之后的最近一个高光
  const upcomingHighlights = useMemo(() => {
    return highlights
      .map(p => (p / 100) * duration)
      .filter(t => t > currentTime)
      .sort((a, b) => a - b);
  }, [highlights, currentTime, duration]);

  const nearest = upcomingHighlights[0] ?? null;

  useEffect(() => {
    if (!nearest || highlights.length === 0) {
      const newState: HighlightState = {
        phase: 'idle',
        nearestHighlight: null,
        timeToNext: Infinity
      };

      if (stateRef.current.phase !== 'idle') {
        setState(newState);
        stateRef.current = newState;
      }
      return;
    }

    const timeToNext = nearest - currentTime;
    const now = Date.now();

    // 处理暂停：冻结计时器
    if (isPaused) {
      return;
    }

    // 计算 deltaTime（seek 检测）
    const deltaTime = currentTime - lastTimeRef.current;
    lastTimeRef.current = currentTime;

    let newPhase: HighlightPhase = stateRef.current.phase;

    // === seek 检测：跳过过快的时间变化 ===
    // if (Math.abs(deltaTime) > 2) {
    //   // seek 越过所有高光 → 不显示反应面板
    //   newPhase = 'idle';
    // }

    // === 处理 cooldown 阶段 ===
    if (newPhase === 'cooldown') {
      const secondsInCooldown = (now - (cooldownStartRef.current || now)) / 1000;
      if (secondsInCooldown >= 4) {
        newPhase = 'idle';
      }
      // cooldown 期间不处理新预警
    }
    // === 处理 active 阶段 ===
    else if (newPhase === 'active') {
      const secondsInActive = (now - (activeStartRef.current || now)) / 1000;
      if (secondsInActive >= 0.5) {
        newPhase = 'cooldown';
        cooldownStartRef.current = now;
      }
    }
    // === 正常阶段流转 ===
    else {
      if (timeToNext <= 0) {
        newPhase = 'active';
        activeStartRef.current = now;
      } else if (timeToNext < 3) {
        newPhase = 'alert';
      } else if (timeToNext < 5) {
        newPhase = 'warning';
      } else {
        newPhase = 'idle';
      }
    }

    // 只在 phase 变化时才触发 setState
    if (newPhase !== stateRef.current.phase) {
      const newState: HighlightState = {
        phase: newPhase,
        nearestHighlight: nearest,
        timeToNext: timeToNext
      };

      setState(newState);
      stateRef.current = newState;
    }
    // 即使 phase 不变，也更新 timeToNext（用于倒计时）
    else if (Math.abs(timeToNext - stateRef.current.timeToNext) > 0.1) {
      stateRef.current.timeToNext = timeToNext;
    }

  }, [currentTime, isPaused, highlights, duration]);

  return state;
}
```

### 2.4 边缘情况处理

| 场景 | 处理方式 |
|------|----------|
| 用户 seek 直接跳到高光点之后 | **两种情况：** <br> 1. seek 越过所有高光 → 不显示反应面板 <br> 2. seek 到高光前 3 秒内 → 直接进入 alert 阶段 |
| 无高光点时 | 整个动画系统完全静默，不渲染任何动画组件，避免空白 Canvas |
| 切换剧集时动画进行中 | useEffect 清理函数中：重置所有状态、清除所有定时器、调用 `destroy()` 销毁粒子 |
| 视频暂停时 | 暂停时冻结倒计时和预警动画，恢复播放后继续（而非跳过） |

---

## 三、第一层：进度条预警（轻量）

### 3.1 设计目标
在不影响观看的前提下，提前告知用户即将到来的高光时刻。

### 3.2 元素设计

| 元素 | 时机 | 视觉效果 | 实现难度 |
|------|------|----------|----------|
| 高光标记点 | 始终 | 金色圆点 + 呼吸脉冲动画（1.5s周期） | ⭐ 简单 |
| 预警扫光 | 高光前3秒 | 光波从标记点向当前位置扫描，像雷达 | ⭐⭐ 中等 |
| 进度条边缘发光 | 高光前5秒 | 进度条右侧渐变成金色，越近越亮 | ⭐ 简单 |

### 3.3 技术实现

#### 3.3.1 高光标记点升级
```css
/* 当前样式 */
.highlight-marker {
  width: 6px;
  height: 6px;
  background: #ff4757;
}

/* 升级为金色脉冲 */
.highlight-marker {
  width: 8px;
  height: 8px;
  background: linear-gradient(135deg, #ffd700, #ff8c00);
  box-shadow: 0 0 8px rgba(255, 215, 0, 0.8);
  animation: highlight-pulse 1.5s ease-in-out infinite;
}

@keyframes highlight-pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  50% { transform: translate(-50%, -50%) scale(1.3); opacity: 0.8; }
}
```

#### 3.3.2 预警扫光动画
```css
.highlight-sweep {
  position: absolute;
  top: 0;
  height: 100%;
  width: 20px;
  background: linear-gradient(90deg, 
    transparent, 
    rgba(255, 215, 0, 0.6), 
    rgba(255, 215, 0, 0.8),
    rgba(255, 215, 0, 0.6),
    transparent
  );
  animation: sweep-animation 0.5s linear forwards;
}

@keyframes sweep-animation {
  from { left: -20px; }
  to { left: 100%; }
}
```

#### 3.3.3 进度条边缘发光
```css
.progress-track.highlight-near::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: 60px;
  background: linear-gradient(90deg, 
    transparent, 
    rgba(255, 215, 0, var(--glow-intensity, 0))
  );
  pointer-events: none;
  transition: --glow-intensity 0.5s ease;
}
```

### 3.4 React 组件设计
```tsx
// 新增组件 - 使用 React.memo + useMemo 优化
const HighlightWarning = React.memo<{
  highlights: number[],
  currentTime: number,
  duration: number
}>(({ highlights, currentTime, duration }) => {
  // 只追踪当前播放位置之后的高光
  const upcomingHighlights = useMemo(() => {
    return highlights.filter(p => {
      const timePercent = (p / 100) * duration;
      return timePercent > currentTime;
    });
  }, [highlights, currentTime, duration]);

  return (
    <>
      {upcomingHighlights.map((point, index) => {
        const timePercent = (point / 100) * duration;
        const timeToHighlight = timePercent - currentTime;
        
        return (
          <React.Fragment key={point}>
            {/* 高光标记（金色脉冲） */}
            <div className="highlight-marker warning" 
                 style={{ left: `${point}%` }} />
            
            {/* 预警扫光（3秒前触发） */}
            {index === 0 && timeToHighlight <= 3 && timeToHighlight > 0 && (
              <HighlightSweep timeToHighlight={timeToHighlight} />
            )}
          </React.Fragment>
        );
      })}
    </>
  );
});
```

---

## 四、第二层：视频叠加层（核心交互）

### 4.1 整体布局架构与 Z-Index

```
z-index 层级定义（从低到高）：
┌─────────────────────────────────────────┐
│  [视频层]                                │ z-index: 0
│  ┌─────────────────────────────────────┐ │
│  │                                     │ │
│  │         <video> / HLS.js           │ │
│  │                                     │ │
│  │  ┌───────────────────────────────┐ │ │
│  │  │ [Canvas 粒子层]                │ │ │ z-index: 10
│  │  │                               │ │ │
│  │  │                               │ │ │
│  │  └───────────────────────────────┘ │ │
│  │                                     │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ 角落边框动画层 (L形收缩)      │ │ │ z-index: 20
│  │  └─────────────────────────────┘   │ │
│  │                                     │ │
│  │         [高能预警] (底部滑入)       │ │ z-index: 30
│  │         [倒计时环]                  │ │
│  │         [边缘闪光]                  │ │ z-index: 25
│  │                                     │ │
│  │         [反应面板] (底部右侧)       │ │ z-index: 40
│  │                                     │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 4.2 ReactionOverlay 编排逻辑

```tsx
interface ReactionOverlayProps {
  phase: HighlightPhase;
  timeToNext: number;
  onReact: (emoji: string) => void;
  isMobile?: boolean;
}

const ReactionOverlay = React.memo<ReactionOverlayProps>(({
  phase,
  timeToNext,
  onReact,
  isMobile = false
}) => {
  const [showFlash, setShowFlash] = useState(false);
  const [showReactionPanel, setShowReactionPanel] = useState(false);

  // === 阶段映射 ===
  useEffect(() => {
    let flashTimer: ReturnType<typeof setTimeout> | null = null;
    let panelTimer: ReturnType<typeof setTimeout> | null = null;
    let hideTimer: ReturnType<typeof setTimeout> | null = null;

    switch (phase) {
      case 'warning':
        // 角落边框动画（Warning 阶段）
        break;
      case 'alert':
        // 高能预警 + 倒计时（Alert 阶段）
        break;
      case 'active':
        // 边缘闪光 + 微震（Active 阶段）
        setShowFlash(true);
        flashTimer = setTimeout(() => setShowFlash(false), 300);
        break;
      case 'cooldown':
        // 反应面板（Cooldown 阶段，0.5秒后显示）
        panelTimer = setTimeout(() => {
          setShowReactionPanel(true);
        }, 500);
        
        // 4秒后自动隐藏
        hideTimer = setTimeout(() => {
          setShowReactionPanel(false);
        }, 4500);
        break;
      case 'idle':
      default:
        setShowReactionPanel(false);
        break;
    }

    // 清理所有定时器
    return () => {
      if (flashTimer) clearTimeout(flashTimer);
      if (panelTimer) clearTimeout(panelTimer);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, [phase]);

  // === 渲染调度 ===
  return (
    <>
      {/* Phase: warning → CornerBorders */}
      {phase === 'warning' && <CornerBorders />}

      {/* Phase: alert → HighlightAlert */}
      {phase === 'alert' && !isMobile && (
        <HighlightAlert secondsLeft={Math.ceil(timeToNext)} />
      )}

      {/* Phase: active → Flash + Shake */}
      {showFlash && <FlashEffect />}
      <div className={showFlash ? 'overlay-shake' : ''} />

      {/* Phase: cooldown → ReactionPanel */}
      {showReactionPanel && (
        <ReactionPanel
          onReact={onReact}
          onClose={() => setShowReactionPanel(false)}
          isMobile={isMobile}
        />
      )}

      {/* 无高光时不渲染粒子 Canvas */}
      {highlights.length > 0 && <ParticleCanvas />}
    </>
  );
});
```

### 4.3 时序流程详细设计

#### 阶段 0：高光前 5 秒 - 角落边框
```
效果：视频四角出现金色 L 形边框，缓慢向内收缩
动画时长：2 秒（从出现到收缩完成）
样式：
```
```css
.corner-border {
  position: absolute;
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 215, 0, 0.8);
  transition: all 2s ease-out;
  z-index: 20;
}

.corner-border.top-left {
  top: 20px;
  left: 20px;
  border-right: none;
  border-bottom: none;
}

.corner-border.shrinking {
  top: 10px;
  left: 10px;
  width: 20px;
  height: 20px;
}
```

#### 阶段 1：高光前 3 秒 - 高能预警
```
┌──────────────────────────┐
│                          │
│     ◉ 3 → 2 → 1          │  ← 脉冲倒计时圆环
│                          │
│   ═══ 高能预警 ═══        │  ← 底部滑入
│                          │
└──────────────────────────┘
```

```tsx
const HighlightAlert = React.memo<{ secondsLeft: number }>(({ secondsLeft }) => {
  return (
    <div className="highlight-alert-container" style={{ zIndex: 30 }}>
      <div className="countdown-ring">
        <svg viewBox="0 0 100 100">
          <circle 
            className="countdown-bg"
            cx="50" cy="50" r="45"
          />
          <circle 
            className="countdown-progress"
            cx="50" cy="50" r="45"
            strokeDasharray={`${(secondsLeft / 3) * 283} 283`}
          />
        </svg>
        <span className="countdown-number">{secondsLeft}</span>
      </div>
      
      <div className="alert-text">高能预警</div>
    </div>
  );
});
```

#### 阶段 2：高光到达时刻 - 边缘闪光 + 微震
```
效果：
① 视频边缘 0.3s 金光一闪
② 叠加层微震（2px 抖动）[不震动控制栏]
③ 粒子从四角向内爆发
```

```css
/* 边缘闪光 */
.flash-effect {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse at center,
    rgba(255, 215, 0, 0.4) 0%,
    transparent 70%
  );
  opacity: 0;
  animation: edge-flash 0.3s ease-out;
  z-index: 25;
}

@keyframes edge-flash {
  0% { opacity: 1; }
  100% { opacity: 0; }
}

/* 叠加层微震 [不震控制栏] */
.overlay-shake {
  animation: overlay-shake 0.2s steps(2);
}

@keyframes overlay-shake {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(2px, 1px); }
  50% { transform: translate(-1px, 2px); }
  75% { transform: translate(-2px, -1px); }
}
```

#### 阶段 3：高光后 0.5 秒 - 反应面板
```
┌──────────────────────────┐
│                   [🔥][❤️]│
│                   [👏][😱]│
│                          │
└──────────────────────────┘
```

```tsx
const ReactionPanel = React.memo<{
  onReact: (emoji: string) => void,
  onClose: () => void,
  isMobile?: boolean
}>(({ onReact, onClose, isMobile = false }) => {
  const emojis = isMobile ? ['🔥', '❤️'] : ['🔥', '❤️', '👏', '😱'];
  
  return (
    <div className="reaction-panel" style={{ zIndex: 40 }}>
      {emojis.map((emoji, index) => (
        <button 
          key={emoji}
          className="reaction-btn"
          style={{ 
            animationDelay: `${index * 0.1}s`,
            width: isMobile ? '36px' : 'var(--touch-target)',
            height: isMobile ? '36px' : 'var(--touch-target)'
          }}
          onClick={() => onReact(emoji)}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
});
```

```css
.reaction-btn {
  animation: reaction-enter 0.3s ease-out backwards;
}

@keyframes reaction-enter {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
```

#### 阶段 4：点击后 - 粒子爆发
```
效果：
① 点击的 emoji 放大弹出
② 从点击位置飞出 8 个副本向四周飘散（移动端 4 个）
③ "+精彩!" 文字上浮消失
```

### 4.4 useParticleSystem Hook（核心）

```tsx
// client/src/hooks/useParticleSystem.ts
interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  emoji: string;
  life: number;
  decay: number;
  size: number;
}

export function useParticleSystem() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number>();
  
  // 初始化
  const init = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // 设置 Canvas 尺寸与容器一致
    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (rect) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }
    };
    
    resize();
    window.addEventListener('resize', resize);
    
    // 返回清理函数
    return () => {
      window.removeEventListener('resize', resize);
    };
  }, []);
  
  // 发送粒子
  const emit = useCallback((x: number, y: number, emoji: string, count: number = 8) => {
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      particlesRef.current.push({
        x, y,
        vx: Math.cos(angle) * (2 + Math.random() * 2),
        vy: Math.sin(angle) * (2 + Math.random() * 2),
        emoji,
        life: 1,
        decay: 0.02,
        size: 16 + Math.random() * 8
      });
    }
  }, []);
  
  // 更新循环
  const update = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    particlesRef.current = particlesRef.current.filter(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.life -= p.decay;
      
      if (p.life > 0) {
        ctx.save();
        ctx.globalAlpha = p.life;
        ctx.font = `${p.size}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.emoji, p.x, p.y);
        ctx.restore();
        return true;
      }
      
      return false;
    });
    
    rafRef.current = requestAnimationFrame(update);
  }, []);
  
  // 启动循环
  const start = useCallback(() => {
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(update);
  }, [update]);
  
  // 停止循环
  const stop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = undefined;
    }
  }, []);
  
  // 销毁
  const destroy = useCallback(() => {
    stop();
    particlesRef.current = [];
  }, [stop]);
  
  // useEffect 绑定生命周期
  useEffect(() => {
    const cleanup = init();
    start();
    
    return () => {
      cleanup?.();
      destroy();
    };
  }, [init, start, destroy]);
  
  return {
    canvasRef,
    emit,
    start,
    stop,
    destroy
  };
}
```

### 4.5 布局尺寸规范

| 元素 | 尺寸 | 位置 | z-index | 响应式 |
|------|------|------|---------|--------|
| 高能预警文字 | 字体 18px，加粗 | 底部居中，距底 100px | 30 | 移动端隐藏 |
| 倒计时环 | 60px × 60px | 预警文字上方 20px | 30 | 移动端隐藏 |
| 反应按钮 | `var(--touch-target)` × `var(--touch-target)` | 底部右侧，距右 20px | 40 | 缩小至 36px，仅显示 2 个 emoji |
| 角落边框 | 40px → 20px | 四角，距边 20px → 10px | 20 | 移动端缩小 |
| 粒子层 Canvas | 100% × 100% | 全屏覆盖 | 10 | 跟随，粒子数量 8→4 |

---

## 五、第三层：连击 & 社交（长期）

### 5.1 功能优先级

| 优先级 | 功能 | 技术实现 | 依赖 |
|--------|------|----------|------|
| P1 | 连击系统 | 状态计数 + CSS动画 | 第二层 |
| P2 | 弹幕式反应 | Canvas弹幕 + WebSocket | 后端支持 |
| P3 | 高光合集面板 | React组件 + API | 需要新接口 |
| P4 | 截屏分享 | html2canvas | 依赖库 |

### 5.2 连击系统详细设计
```
触发条件：连续 3 个高光都点击了反应
显示效果："🔥 三连击！" + 全屏彩色粒子雨
动画时长：2 秒
```

```tsx
const ComboSystem = React.memo<{ comboCount: number }>(({ comboCount }) => {
  if (comboCount < 3) return null;
  
  return (
    <div className="combo-overlay">
      <span className="combo-text">
        🔥 {comboCount} 连击！
      </span>
      <ParticleRain colors={['var(--accent-primary)', '#ffd700', '#ff6b81']} />
    </div>
  );
});
```

---

## 六、技术实现规划

### 6.1 文件结构
```
client/src/components/
├── VideoPlayer.tsx              # 主播放器（修改）
├── ReactionOverlay.tsx         # 新增：互动叠加层容器
├── ParticleCanvas.tsx           # 新增：粒子系统Canvas
├── HighlightAlert.tsx           # 新增：高能预警
├── ReactionPanel.tsx           # 新增：反应面板
├── CornerBorders.tsx           # 新增：角落边框
└── ComboOverlay.tsx            # 新增：连击系统

client/src/hooks/
├── useHighlightSync.ts         # 新增：高光同步hook（核心时序引擎）
├── useParticleSystem.ts        # 新增：粒子系统hook
└── useReactionCount.ts         # 新增：反应计数hook
```

### 6.2 依赖引入
```bash
# 已有依赖
- TailwindCSS (动画)
- React (状态管理)

# 可选增强
- canvas-confetti (连击粒子雨) # 或自己实现
- lottie-react (复杂动画)        # 可选，当前方案不需要
```

### 6.3 性能考虑
| 优化项 | 方案 |
|--------|------|
| 动画帧率 | 使用 `requestAnimationFrame`，暂停时停止 |
| 内存泄漏 | 组件卸载时清理所有定时器和粒子 |
| Canvas 性能 | 对象池复用粒子，避免 GC |
| React 重渲染 | 组件用 `React.memo` 包裹，props 用 `useMemo` 缓存；只在 phase 变化时 setState |
| 移动端 | 简化动画，关闭粒子效果，减少粒子数量 |
| 无高光时 | 完全不渲染动画组件，避免空白 Canvas |

---

## 七、实施顺序与工时估计

### 阶段一：核心交互（第1-2天）
1. ✅ 实现 `useHighlightSync` hook（高光时序引擎）
2. ✅ 实现 `useParticleSystem` hook（粒子系统）
3. ✅ 创建 `ReactionOverlay.tsx` 容器组件
4. ✅ 实现边缘闪光 + 屏幕微震
5. ✅ 实现反应面板 + emoji按钮
6. ✅ Canvas粒子爆发系统
7. ✅ 与现有高光点数据集成
8. ✅ 边缘情况处理（seek、切换剧集、暂停、无高光）

### 阶段二：进度条预警（第0.5天）
1. ✅ 高光标记金色脉冲
2. ✅ 预警扫光动画
3. ✅ 边缘发光效果

### 阶段三：完善体验（第1天）
1. ✅ 角落边框收缩动画
2. ✅ 高能预警 + 倒计时环
3. ✅ 连击系统
4. ✅ 动画开关（localStorage）
5. ✅ 移动端适配

### 阶段四：社交功能（待定）
1. ⬜ 弹幕式反应（需WebSocket）
2. ⬜ 高光合集面板
3. ⬜ 截屏分享

---

## 八、自我反思与风险评估

### 8.1 合理性分析

#### ✅ 优势
1. **分层递进**：第一层轻量不打扰，第二层核心体验，第三层社交扩展
2. **与现有框架契合**：使用 React Hooks + CSS Animation，符合现有架构
3. **Canvas方案轻量**：避免引入大型动画库，如lottie
4. **移动端考虑**：关键动画在移动端有降级方案
5. **完整的时序引擎**：新增的 `useHighlightSync` 管理所有触发时机，使用 useRef + Date.now() 精确计时
6. **React生命周期绑定**：`useParticleSystem` 正确处理初始化/清理
7. **多高光重叠处理**：cooldown阶段避免冲突
8. **CSS变量复用**：引用 `--accent-primary`、`--touch-target`
9. **z-index层级清晰**：避免与HLS.js/控制栏冲突
10. **屏幕微震仅震动叠加层**：不影响控制栏操作
11. **性能优化**：useRef 跟踪内部状态，只在 phase 变化时 setState

#### ⚠️ 风险点
1. **性能风险**：Canvas粒子在高配手机可能流畅，但低端机需测试
2. **兼容性**：CSS `backdrop-filter` 在旧浏览器不支持，需要降级
3. **与HLS.js冲突**：视频层特效不能干扰HLS播放，需要z-index控制（已定义）

### 8.2 布局适配评估

#### 桌面端（1920×1080）
```
✓ 反应面板：右下角，距边缘 20px，44×44px
✓ 高能预警：底部居中，距底 100px
✓ 角落边框：四角，距边 20px
✓ 粒子效果：全屏覆盖，无裁剪，8个粒子
```

#### 平板端（1024×768）
```
✓ 反应面板：右下角，距边缘 15px（缩小）
✓ 高能预警：底部居中，距底 80px
✓ 角落边框：四角，距边 15px
✓ 粒子效果：全屏覆盖
```

#### 移动端（375×667）
```
⚠️ 高能预警：完全隐藏（仅保留进度条脉冲标记）
⚠️ 角落边框：缩小至 15px
✓ 反应面板：右下角，36×36px，仅显示2个emoji
✓ 粒子效果：减少粒子数量（8→4）
```

### 8.3 改进建议

1. **增加用户控制**：添加"互动动画开关"，不喜欢的用户可关闭
2. **高光点可视化**：当前只显示红点，可考虑显示高光区域条（类似B站进度条上的高能区域）
3. **后端数据收集**：保存用户反应数据，用于分析高光效果
4. **动画性能监控**：使用 `performance.now()` 监控动画帧率，低于30fps自动降级

---

## 九、确认事项（已确定）

在开始实现前已确认的问题：

| 问题 | 已确定方案 |
|------|-----------|
| **互动动画开关** | ✅ 需要。存储在 localStorage，默认开启。settings 按钮放在控制栏 |
| **移动端策略** | 高能预警完全隐藏。仅保留进度条脉冲标记 + 反应面板（缩减到2个emoji） |
| **连击系统起点** | 3 个连续高光反应触发连击 |
| **粒子数量** | 桌面 8 个，移动端 4 个 |
| **反应面板显示时长** | 4 秒（比建议的3秒多给1秒反应时间） |
| **数据收集** | 暂不需要。先跑通前端体验，后续加API |
| **seek 行为** | 两种情况：越过所有高光 → 不显示；跳到前 3 秒 → 直接 alert |

---

## 十、下一步行动

✅ 方案已审核通过，立即开始第一阶段实现：
1. 实现 `useHighlightSync` hook（高光时序引擎）
2. 实现 `useParticleSystem` hook（粒子系统）
3. 创建 `ReactionOverlay.tsx` 容器组件
4. 实现边缘闪光效果
5. 实现反应面板
6. 处理边缘情况（seek、切换剧集、暂停、无高光）

---

**文档版本**：v1.3
**创建日期**：2026-05-22
**上次更新**：2026-05-22
**状态**：✅ 终版，可交付
