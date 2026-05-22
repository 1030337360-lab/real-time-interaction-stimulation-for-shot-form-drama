const Redis = require('ioredis');

// Redis 客户端（带自动重连和降级）
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
let redis = null;
let redisAvailable = false;
let globalDb = null;

function setGlobalDb(db) {
  globalDb = db;
}

async function connectRedis() {
  try {
    redis = new Redis(REDIS_URL, {
      maxRetriesPerRequest: 3,
      retryStrategy(times) {
        if (times > 5) {
          console.warn('Redis: too many retries, giving up. Using lowdb fallback.');
          return null; // 停止重试
        }
        return Math.min(times * 200, 2000);
      },
      lazyConnect: true,
    });

    redis.on('error', (err) => {
      if (redisAvailable) {
        console.error('Redis connection error:', err.message);
        redisAvailable = false;
      }
    });

    redis.on('connect', () => {
      console.log('Redis connected');
      redisAvailable = true;
    });

    redis.on('close', () => {
      console.warn('Redis connection closed');
      redisAvailable = false;
    });

    await redis.connect();
    await redis.ping();
    redisAvailable = true;
    console.log('Redis: connected and ready');
    return true;
  } catch (err) {
    console.warn(`Redis unavailable (${err.message}), falling back to lowdb`);
    redisAvailable = false;
    redis = null;
    return false;
  }
}

function isRedisReady() {
  return redisAvailable && redis && redis.status === 'ready';
}

// ============================================================
// Sessions（优先 Redis TTL，降级 lowdb）
// ============================================================
const SESSION_PREFIX = 'session:';
const SESSION_TTL = 30 * 24 * 60 * 60; // 30 天

async function getSession(userId) {
  if (isRedisReady()) {
    try {
      const data = await redis.get(`${SESSION_PREFIX}${userId}`);
      return data ? JSON.parse(data) : undefined;
    } catch (err) {
      console.error('Redis getSession error:', err.message);
    }
  }
  // 降级到 lowdb
  return (globalDb && globalDb.data && globalDb.data.sessions)
    ? globalDb.data.sessions[userId] : undefined;
}

async function setSession(userId, data) {
  const sessionData = { ...data, lastActive: Date.now() };
  
  if (isRedisReady()) {
    try {
      await redis.set(
        `${SESSION_PREFIX}${userId}`,
        JSON.stringify(sessionData),
        'EX',
        SESSION_TTL
      );
      return;
    } catch (err) {
      console.error('Redis setSession error:', err.message);
    }
  }
  // 降级到 lowdb
  if (globalDb && globalDb.data) {
    if (!globalDb.data.sessions) globalDb.data.sessions = {};
    globalDb.data.sessions[userId] = sessionData;
  }
}

async function deleteSession(userId) {
  if (isRedisReady()) {
    try {
      await redis.del(`${SESSION_PREFIX}${userId}`);
      return;
    } catch (err) {
      console.error('Redis deleteSession error:', err.message);
    }
  }
  // 降级到 lowdb
  if (globalDb && globalDb.data && globalDb.data.sessions) {
    delete globalDb.data.sessions[userId];
  }
}

// Redis 自动过期，不需要清理函数
// 降级模式时保留原 lowdb cleanupSessions（在 app.js 中）

// ============================================================
// Video Cache（Redis 带 TTL，自动淘汰）
// ============================================================
const CACHE_PREFIX = 'vcache:';
const CACHE_TTL = 600; // 10 分钟

async function getVideoCache(key) {
  if (isRedisReady()) {
    try {
      const data = await redis.get(`${CACHE_PREFIX}${key}`);
      return data ? JSON.parse(data) : undefined;
    } catch (err) {
      console.error('Redis getVideoCache error:', err.message);
    }
  }
  return undefined; // 降级时跳过缓存
}

async function setVideoCache(key, data) {
  if (isRedisReady()) {
    try {
      await redis.set(`${CACHE_PREFIX}${key}`, JSON.stringify(data), 'EX', CACHE_TTL);
    } catch (err) {
      console.error('Redis setVideoCache error:', err.message);
    }
  }
}

async function clearVideoCache(pattern) {
  if (isRedisReady()) {
    try {
      const keys = await redis.keys(`${CACHE_PREFIX}${pattern || '*'}`);
      if (keys.length > 0) {
        await redis.del(...keys);
      }
      return keys.length;
    } catch (err) {
      console.error('Redis clearVideoCache error:', err.message);
      return 0;
    }
  }
  return 0;
}

// ============================================================
// Highlights（Redis 缓存，JSON 持久化）
// ============================================================
const HIGHLIGHT_PREFIX = 'highlight:';

async function getHighlights(episodeId) {
  if (isRedisReady()) {
    try {
      const data = await redis.get(`${HIGHLIGHT_PREFIX}${episodeId}`);
      if (data) return JSON.parse(data);
    } catch (err) {
      console.error('Redis getHighlights error:', err.message);
    }
  }
  // 从 lowdb 读取
  if (globalDb && globalDb.data && globalDb.data.highlights) {
    const h = globalDb.data.highlights.find(h => h.episode_id === episodeId);
    return h ? h.points : [];
  }
  return [];
}

async function setHighlights(episodeId, points) {
  // 先写 lowdb（source of truth）
  if (globalDb && globalDb.data) {
    if (!globalDb.data.highlights) globalDb.data.highlights = [];
    const idx = globalDb.data.highlights.findIndex(h => h.episode_id === episodeId);
    const entry = { episode_id: episodeId, points, updated_at: new Date().toISOString() };
    if (idx >= 0) {
      globalDb.data.highlights[idx] = entry;
    } else {
      globalDb.data.highlights.push(entry);
    }
  }
  
  // 同步写 Redis 缓存
  if (isRedisReady()) {
    try {
      await redis.set(`${HIGHLIGHT_PREFIX}${episodeId}`, JSON.stringify(points), 'EX', 3600);
    } catch (err) {
      console.error('Redis setHighlights error:', err.message);
    }
  }
}

// ============================================================
// 工具函数
// ============================================================
async function getCacheStatus() {
  if (isRedisReady()) {
    try {
      const keys = await redis.keys(`${CACHE_PREFIX}*`);
      const sessionKeys = await redis.keys(`${SESSION_PREFIX}*`);
      return {
        backend: 'redis',
        cacheKeys: keys.length,
        sessionKeys: sessionKeys.length,
        redisConnected: true,
      };
    } catch (err) {
      return { backend: 'redis', error: err.message };
    }
  }
  return { backend: 'lowdb', redisConnected: false };
}

// 优雅关闭
async function closeRedis() {
  if (redis) {
    try {
      await redis.quit();
      console.log('Redis disconnected');
    } catch (err) {
      redis.disconnect();
    }
  }
}

module.exports = {
  connectRedis,
  closeRedis,
  isRedisReady,
  setGlobalDb,
  getSession,
  setSession,
  deleteSession,
  getVideoCache,
  setVideoCache,
  clearVideoCache,
  getHighlights,
  setHighlights,
  getCacheStatus,
};
