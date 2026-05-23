require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { Low } = require('lowdb');
const { JSONFile } = require('lowdb/node');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const redisModule = require('./redis');

const app = express();
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  console.error('FATAL: JWT_SECRET environment variable is not set!');
  console.error('Please create a .env file with: JWT_SECRET=<your-secret-key>');
  process.exit(1);
};
const JWT_EXPIRES_IN = '2h';
const REFRESH_EXPIRES_IN = '30d';

// F1+F4: sessions 通过 Redis 模块管理（Redis TTL 自动过期，降级 lowdb）
// Redis 可用时用 Redis（30天 TTL），不可用时降级到 lowdb
const getSession = redisModule.getSession;
const setSession = redisModule.setSession;
const deleteSession = redisModule.deleteSession;
const setGlobalDb = redisModule.setGlobalDb;

// 降级模式时清理过期 lowdb sessions
function cleanupSessions() {
  if (!db || !db.data || !db.data.sessions) return;
  const now = Date.now();
  const thirtyDays = 30 * 24 * 60 * 60 * 1000;
  let cleaned = 0;
  for (const userId of Object.keys(db.data.sessions)) {
    if (now - db.data.sessions[userId].lastActive > thirtyDays) {
      delete db.data.sessions[userId];
      cleaned++;
    }
  }
  if (cleaned > 0) console.log(`[lowdb] Cleaned ${cleaned} expired sessions`);
}

app.use(helmet());
app.use(cors({
  credentials: true,
  origin: true
}));
app.use(express.json());
app.use(express.static('public'));

// 减少 TIME_WAIT：延长 Keep-Alive 超时 + 复用连接
app.use((req, res, next) => {
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Keep-Alive', 'timeout=60, max=1000');
  next();
});

app.use((req, res, next) => {
  if (!db) return res.status(503).json({ error: 'Database not initialized' });
  next();
});

app.get('/api/test/:dramaName/:filename', (req, res) => {
  const { dramaName, filename } = req.params;
  console.log('Test - dramaName:', dramaName);
  console.log('Test - filename:', filename);
  const fullPath = path.join(externalVideoDir, dramaName, filename);
  console.log('Test - fullPath:', fullPath);
  console.log('Test - exists:', fs.existsSync(fullPath));
  res.json({ dramaName, filename, fullPath, exists: fs.existsSync(fullPath) });
});

const videoDir = path.join(__dirname, 'videos');
const coverDir = path.join(__dirname, 'covers');
const dbDir = path.join(__dirname, 'database');

const externalBaseDir = 'D:\\video_data';
const externalVideoDir = path.join(externalBaseDir, 'videos');
const externalCoverDir = path.join(externalBaseDir, 'pictures');
const externalPosterDir = path.join(externalBaseDir, 'posters');

if (!fs.existsSync(videoDir)) fs.mkdirSync(videoDir, { recursive: true });
if (!fs.existsSync(coverDir)) fs.mkdirSync(coverDir, { recursive: true });
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });
if (!fs.existsSync(externalPosterDir)) fs.mkdirSync(externalPosterDir, { recursive: true });

const dbPath = path.join(dbDir, 'drama.json');
const cacheConfig = {
  currentEpisode: { maxBuffer: 30 },
  otherEpisodes: { maxBuffer: 10 },
  maxCachedOtherEpisodes: 5
};
// videoCache 改为 Redis 管理（10min TTL），降级时使用 Map
const videoCache = redisModule.isRedisReady() ? null : new Map();

function getCachedVideo(key) {
  return redisModule.getVideoCache(key);
}
function setCachedVideo(key, data) {
  if (videoCache) {
    videoCache.set(key, data);
  }
  redisModule.setVideoCache(key, data);
}

let db;
let globalDb;

async function initDatabase() {
  const adapter = new JSONFile(dbPath);
  db = new Low(adapter, { 
    dramas: [], 
    episodes: [], 
    play_history: [], 
    episode_posters: [], 
    highlights: [],
    users: [],
    sessions: {}
  });
  await db.read();
  // F1: 确保 sessions 字段存在
  if (!db.data.sessions) db.data.sessions = {};
  if (!db.data.users) db.data.users = [];
  // 暴露给 Redis 模块降级使用
  globalDb = db;
  setGlobalDb(db);
  console.log('Connected to JSON database');
}

let isScanning = false;

function generatePoster(videoPath, posterPath) {
  return new Promise((resolve, reject) => {
    if (fs.existsSync(posterPath)) {
      return resolve();
    }
    const dir = path.dirname(posterPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const ffmpeg = spawn('ffmpeg', [
      '-ss', '00:00:01',
      '-i', videoPath,
      '-vframes', '1',
      '-q:v', '2',
      '-y',
      posterPath
    ]);
    let stderr = '';
    ffmpeg.stderr.on('data', (data) => { stderr += data.toString(); });
    ffmpeg.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        console.error(`ffmpeg failed for ${videoPath}: ${stderr.slice(-200)}`);
        reject(new Error(`ffmpeg exited with code ${code}`));
      }
    });
    ffmpeg.on('error', (err) => {
      console.error(`ffmpeg spawn error for ${videoPath}:`, err.message);
      reject(err);
    });
  });
}

async function scanVideoDirectory() {
  if (isScanning) {
    console.log('Scan already in progress, skipping...');
    return;
  }
  
  isScanning = true;
  try {
    if (!fs.existsSync(externalVideoDir)) {
      console.log(`External video directory not found: ${externalVideoDir}`);
      return;
    }

    await db.read();
    
    const videoExtensions = ['.mp4', '.mkv', '.webm', '.mov', '.m3u8'];
    const coverExtensions = ['.jpg', '.jpeg', '.png', '.webp'];

    const dramaDirectories = fs.readdirSync(externalVideoDir, { withFileTypes: true })
      .filter(dir => dir.isDirectory())
      .map(dir => dir.name);

    db.data.dramas = [];
    db.data.episodes = [];

    for (const dramaName of dramaDirectories) {
      const dramaVideoPath = path.join(externalVideoDir, dramaName);
      const files = fs.readdirSync(dramaVideoPath);

      const videoFiles = files.filter(f => 
        videoExtensions.includes(path.extname(f).toLowerCase())
      ).sort((a, b) => {
        const numA = parseInt(a.match(/\d+/)?.[0] || '0');
        const numB = parseInt(b.match(/\d+/)?.[0] || '0');
        return numA - numB;
      });

      if (videoFiles.length === 0) {
        continue;
      }

      let coverUrl = null;
      if (fs.existsSync(externalCoverDir)) {
        const coverFiles = fs.readdirSync(externalCoverDir);
        const matchedCover = coverFiles.find(f => 
          coverExtensions.includes(path.extname(f).toLowerCase()) && 
          f.toLowerCase().startsWith(dramaName.toLowerCase())
        );
        if (matchedCover) {
          coverUrl = matchedCover;
        }
      }

      const newId = db.data.dramas.length > 0 
        ? Math.max(...db.data.dramas.map(d => d.id)) + 1 
        : 1;

      const drama = {
        id: newId,
        title: dramaName,
        description: `短剧《${dramaName}》`,
        cover_url: coverUrl,
        video_url: `${dramaName}/${videoFiles[0]}`,
        episode_count: videoFiles.length,
        created_at: new Date().toISOString(),
      };

      db.data.dramas.push(drama);

      for (let i = 0; i < videoFiles.length; i++) {
        const episodeId = db.data.episodes.length > 0 
          ? Math.max(...db.data.episodes.map(e => e.id)) + 1 
          : 1;
        
        const videoFileName = videoFiles[i];
        const episodeTitle = path.parse(videoFileName).name;
        const videoPath = path.join(dramaVideoPath, videoFileName);
        const posterFileName = `${episodeTitle}.jpg`;
        const posterPath = path.join(externalPosterDir, dramaName, posterFileName);

        try {
          await generatePoster(videoPath, posterPath);
        } catch (err) {
          console.warn(`Failed to generate poster for ${dramaName}/${videoFileName}:`, err.message);
        }

        db.data.episodes.push({
          id: episodeId,
          drama_id: newId,
          title: episodeTitle,
          cover_url: coverUrl,
          video_url: `${dramaName}/${videoFileName}`,
          episode_number: i + 1,
        });
      }

      console.log(`Added drama: ${dramaName} (${videoFiles.length} episodes)`);
    }

    await db.write();
    console.log('Video directory scan completed');
  } catch (err) {
    console.error('Error scanning video directory:', err);
  } finally {
    isScanning = false;
  }
}

app.get('/api/dramas', async (req, res) => {
  try {
    const dramas = db.data.dramas.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    res.json(dramas);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/dramas/:id', async (req, res) => {
  const { id } = req.params;
  try {
    const drama = db.data.dramas.find(d => d.id === parseInt(id));
    if (!drama) return res.status(404).json({ error: 'Drama not found' });
    res.json(drama);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/cache/status', async (req, res) => {
  const redisStatus = await redisModule.getCacheStatus();
  const cacheArray = videoCache ? Array.from(videoCache.entries()).map(([key, value]) => ({
    key,
    ...value
  })) : [];
  res.json({
    backend: redisStatus.backend,
    redisConnected: redisStatus.redisConnected,
    cacheSize: videoCache ? videoCache.size : redisStatus.cacheKeys || 0,
    config: cacheConfig,
    entries: cacheArray.slice(0, 20), // 只返回前 20 条
  });
});

app.post('/api/cache/clear', async (req, res) => {
  const { episodeKeys } = req.body;
  let cleared = 0;
  
  if (episodeKeys && Array.isArray(episodeKeys)) {
    if (videoCache) {
      episodeKeys.forEach(key => videoCache.delete(key));
    }
    cleared = await redisModule.clearVideoCache('*');
  } else {
    if (videoCache) videoCache.clear();
    cleared = await redisModule.clearVideoCache('*');
  }
  res.json({ message: 'Cache cleared', clearedKeys: cleared });
});

function getPosterUrl(videoUrl) {
  if (!videoUrl) return null;
  const parts = videoUrl.split('/');
  if (parts.length < 2) return null;
  const fileName = path.parse(parts[parts.length - 1]).name;
  const dramaName = parts[parts.length - 2];
  return `${dramaName}/${fileName}.jpg`;
}

app.get('/api/episodes/:dramaId', async (req, res) => {
  const { dramaId } = req.params;
  try {
    const episodes = db.data.episodes.filter(e => e.drama_id === parseInt(dramaId))
      .sort((a, b) => a.episode_number - b.episode_number);
    
    if (episodes.length === 0) {
      const drama = db.data.dramas.find(d => d.id === parseInt(dramaId));
      if (drama) {
        const mockEpisodes = [];
        const baseDir = drama.video_url.substring(0, drama.video_url.lastIndexOf('/') + 1);
        const match = drama.video_url.match(/第(\d+)集/);
        const startEpisode = match ? parseInt(match[1]) : 1;
        
        for (let i = 1; i <= drama.episode_count; i++) {
          const episodeNumber = startEpisode + i - 1;
          const episodeTitle = `第${episodeNumber}集`;
          const videoUrl = `${baseDir}${episodeTitle}.mp4`;
          mockEpisodes.push({
            id: i,
            drama_id: drama.id,
            title: episodeTitle,
            cover_url: drama.cover_url,
            video_url: videoUrl,
            episode_number: i,
            poster_url: getPosterUrl(videoUrl)
          });
        }
        return res.json(mockEpisodes);
      }
    }
    
    const episodesWithPosters = episodes.map(ep => ({
      ...ep,
      poster_url: getPosterUrl(ep.video_url)
    }));
    
    res.json(episodesWithPosters);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/posters/:dramaName/:filename', (req, res) => {
  const { dramaName, filename } = req.params;
  const posterPath = path.join(externalPosterDir, dramaName, filename);
  if (fs.existsSync(posterPath)) {
    return res.sendFile(posterPath);
  }
  res.status(404).json({ error: 'Poster not found' });
});

app.post('/api/episodes/:episodeId/poster', async (req, res) => {
  const { episodeId } = req.params;
  const { poster_url } = req.body;
  
  try {
    if (!db.data.episode_posters) {
      db.data.episode_posters = [];
    }
    
    const existingIndex = db.data.episode_posters.findIndex(p => p.episode_id === parseInt(episodeId));
    
    if (existingIndex >= 0) {
      db.data.episode_posters[existingIndex].poster_url = poster_url;
      db.data.episode_posters[existingIndex].updated_at = new Date().toISOString();
    } else {
      db.data.episode_posters.push({
        episode_id: parseInt(episodeId),
        poster_url,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      });
    }
    
    await db.write();
    res.json({ success: true, episodeId: parseInt(episodeId) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/video/:dramaName/:filename', (req, res) => {
  const { dramaName, filename } = req.params;
  const maxBuffer = parseInt(req.query.maxBuffer) || cacheConfig.otherEpisodes.maxBuffer;
  const isCurrent = req.query.current === 'true';
  
  const actualMaxBuffer = isCurrent ? cacheConfig.currentEpisode.maxBuffer : maxBuffer;
  const videoKey = `${dramaName}/${filename}`;
  
  const externalPath = path.join(externalVideoDir, dramaName, filename);
  const localPath = path.join(videoDir, dramaName, filename);
  const fallbackPath = path.join(videoDir, filename);

  let filePath = null;
  if (fs.existsSync(externalPath)) {
    filePath = externalPath;
  } else if (fs.existsSync(localPath)) {
    filePath = localPath;
  } else if (fs.existsSync(fallbackPath)) {
    filePath = fallbackPath;
  }

  if (filePath) {
    setCachedVideo(videoKey, {
      accessed: true,
      lastAccess: Date.now(),
      maxBuffer: actualMaxBuffer
    });
    return streamVideo(filePath, req, res);
  }

  res.status(404).json({ error: 'Video not found' });
});

app.get('/api/video/:filename', (req, res) => {
  const { filename } = req.params;
  const filePath = path.join(videoDir, filename);

  if (!fs.existsSync(filePath)) {
    const fallbackPath = path.join(__dirname, 'public', filename);
    if (fs.existsSync(fallbackPath)) {
      return streamVideo(fallbackPath, req, res);
    }
    return res.status(404).json({ error: 'Video not found' });
  }

  streamVideo(filePath, req, res);
});

function streamVideo(filePath, req, res) {
  if (!fs.existsSync(filePath)) {
    console.error('Video file not found:', filePath);
    return res.status(404).json({ error: 'Video file not found' });
  }

  const stat = fs.statSync(filePath);
  const fileSize = stat.size;
  const range = req.headers.range;

  const baseHeaders = {
    'Content-Type': 'video/mp4',
    'Accept-Ranges': 'bytes',
    'Cache-Control': 'private, max-age=300',
    'Pragma': 'no-cache',
    'Expires': '0',
    'Connection': 'keep-alive',
    'Keep-Alive': 'timeout=60, max=100',
  };

  if (range) {
    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    
    if (start >= fileSize || end >= fileSize || start > end) {
      res.writeHead(416, {
        ...baseHeaders,
        'Content-Range': `bytes */${fileSize}`,
      });
      return res.end();
    }

    const chunksize = end - start + 1;
    const head = {
      ...baseHeaders,
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Content-Length': chunksize,
    };
    res.writeHead(206, head);

    const file = fs.createReadStream(filePath, { start, end });
    
    file.on('error', (err) => {
      console.error('Stream error:', err);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Stream error' });
      } else {
        res.end();
      }
    });

    file.pipe(res);
  } else {
    const head = {
      ...baseHeaders,
      'Content-Length': fileSize,
    };
    res.writeHead(200, head);

    const file = fs.createReadStream(filePath);
    
    file.on('error', (err) => {
      console.error('Stream error:', err);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Stream error' });
      } else {
        res.end();
      }
    });

    file.pipe(res);
  }
}

app.get('/covers/:filename', (req, res) => {
  const { filename } = req.params;
  
  const externalPath = path.join(externalCoverDir, filename);
  if (fs.existsSync(externalPath)) {
    return res.sendFile(externalPath);
  }

  const localPath = path.join(coverDir, filename);
  if (fs.existsSync(localPath)) {
    return res.sendFile(localPath);
  }

  const fallbackPath = path.join(__dirname, 'public', 'covers', filename);
  if (fs.existsSync(fallbackPath)) {
    return res.sendFile(fallbackPath);
  }

  res.status(404).json({ error: 'Cover not found' });
});

app.post('/api/history', async (req, res) => {
  const { drama_id, episode_id, progress } = req.body;
  
  // P0#1: 输入校验
  if (
    typeof drama_id !== 'number' || 
    !Number.isInteger(drama_id) || 
    drama_id <= 0
  ) {
    return res.status(400).json({ 
      error: 'Invalid drama_id: must be a positive integer' 
    });
  }
  
  if (
    typeof episode_id !== 'number' || 
    !Number.isInteger(episode_id) || 
    episode_id <= 0
  ) {
    return res.status(400).json({ 
      error: 'Invalid episode_id: must be a positive integer' 
    });
  }
  
  if (
    typeof progress !== 'number' || 
    progress < 0 || 
    progress > 86400 // 最多24小时
  ) {
    return res.status(400).json({ 
      error: 'Invalid progress: must be a number between 0 and 86400' 
    });
  }
  
  try {
    const existingIndex = db.data.play_history.findIndex(h => h.drama_id === drama_id);
    
    if (existingIndex >= 0) {
      db.data.play_history[existingIndex] = {
        ...db.data.play_history[existingIndex],
        episode_id,
        progress,
        updated_at: new Date().toISOString(),
      };
    } else {
      const newId = db.data.play_history.length > 0 
        ? Math.max(...db.data.play_history.map(h => h.id)) + 1 
        : 1;
      db.data.play_history.push({
        id: newId,
        drama_id,
        episode_id,
        progress,
        updated_at: new Date().toISOString(),
      });
    }
    
    await db.write();
    res.json({ id: drama_id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/history/:drama_id', async (req, res) => {
  const { drama_id } = req.params;
  try {
    const history = db.data.play_history.find(h => h.drama_id === parseInt(drama_id));
    res.json(history || { progress: 0 });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/scan', async (req, res) => {
  try {
    await scanVideoDirectory();
    res.json({ message: 'Scan completed successfully' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/internal/highlights', async (req, res) => {
  const { episode_id, points } = req.body;
  
  if (!episode_id || !points || !Array.isArray(points)) {
    return res.status(400).json({ error: 'Invalid request: episode_id and points array are required' });
  }
  
  const validPoints = points.filter(p => 
    typeof p === 'number' && p >= 0 && p <= 100
  );
  
  if (validPoints.length === 0) {
    return res.status(400).json({ error: 'Invalid points: must be array of numbers between 0 and 100' });
  }
  
  try {
    // 写 Redis 缓存 + lowdb 持久化（redis.setHighlights 双写）
    await redisModule.setHighlights(episode_id, validPoints);
    await db.write();
    res.json({ success: true, episode_id, count: validPoints.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/episodes/:episodeId/highlights', async (req, res) => {
  const { episodeId } = req.params;
  
  try {
    const points = await redisModule.getHighlights(parseInt(episodeId));
    res.json(points);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/internal/highlights/:episodeId', async (req, res) => {
  const { episodeId } = req.params;
  
  try {
    if (!db.data.highlights) {
      return res.json({ success: true, deleted: 0 });
    }
    
    const initialLength = db.data.highlights.length;
    db.data.highlights = db.data.highlights.filter(h => h.episode_id !== parseInt(episodeId));
    
    if (db.data.highlights.length !== initialLength) {
      await db.write();
    }
    
    res.json({ success: true, deleted: initialLength - db.data.highlights.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

function generateToken(userId) {
  const accessToken = jwt.sign({ userId }, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
  const refreshToken = jwt.sign({ userId }, JWT_SECRET, { expiresIn: REFRESH_EXPIRES_IN });
  return { accessToken, refreshToken };
}

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    req.user = null;
    return next();
  }
  
  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      req.user = null;
      return next();
    }
    
    const session = getSession(user.userId);
    if (!session || session.accessToken !== token) {
      // F2: 改为直接返回 401，不再静默放行
      return res.status(401).json({ error: 'Invalid or expired token' });
    }
    
    req.user = { id: user.userId };
    next();
  });
}

app.post('/api/auth/register', async (req, res) => {
  const { username, password, phone } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }
  
  // F6: 输入校验
  if (typeof username !== 'string' || username.length < 3 || username.length > 20) {
    return res.status(400).json({ error: 'Username must be 3-20 characters' });
  }
  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    return res.status(400).json({ error: 'Username can only contain letters, numbers, and underscores' });
  }
  if (typeof password !== 'string' || password.length < 6 || password.length > 100) {
    return res.status(400).json({ error: 'Password must be 6-100 characters' });
  }
  
  try {
    if (!db.data.users) {
      db.data.users = [];
    }
    
    // F8: phone 去重只在 phone 有值时检查
    const existingUser = db.data.users.find(u => u.username === username || (phone && u.phone === phone));
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }
    
    const hashedPassword = await bcrypt.hash(password, 10);
    const newId = db.data.users.length > 0 
      ? Math.max(...db.data.users.map(u => u.id)) + 1 
      : 1;
    
    const newUser = {
      id: newId,
      username,
      password: hashedPassword,
      phone: phone || null,
      email: null,
      avatar: null,
      nickname: username,
      role: 'user',
      status: 'active',
      metadata: {
        watch_count: 0,
        favorite_count: 0,
        last_login: null,
        created_at: new Date().toISOString(),
        preferences: {}
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    
    db.data.users.push(newUser);
    await db.write();
    
    const { accessToken, refreshToken } = generateToken(newId);
    setSession(newId, { accessToken, refreshToken });
    
    res.status(201).json({
      success: true,
      user: {
        id: newId,
        username,
        nickname: newUser.nickname,
        avatar: newUser.avatar,
        role: newUser.role
      },
      accessToken,
      refreshToken
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/auth/login', async (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }
  
  try {
    if (!db.data.users) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const user = db.data.users.find(u => u.username === username || u.phone === username);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const isValid = await bcrypt.compare(password, user.password);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    if (user.status !== 'active') {
      return res.status(401).json({ error: 'Account is not active' });
    }
    
    user.metadata.last_login = new Date().toISOString();
    user.updated_at = new Date().toISOString();
    await db.write();
    
    const { accessToken, refreshToken } = generateToken(user.id);
    setSession(user.id, { accessToken, refreshToken });
    
    res.json({
      success: true,
      user: {
        id: user.id,
        username: user.username,
        nickname: user.nickname,
        avatar: user.avatar,
        role: user.role
      },
      accessToken,
      refreshToken
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/auth/refresh', async (req, res) => {
  const { refreshToken } = req.body;
  
  if (!refreshToken) {
    return res.status(400).json({ error: 'Refresh token is required' });
  }
  
  try {
    const decoded = jwt.verify(refreshToken, JWT_SECRET);
    const userId = decoded.userId;
    
    const session = sessions.get(userId);
    if (!session || session.refreshToken !== refreshToken) {
      return res.status(401).json({ error: 'Invalid refresh token' });
    }
    
    const { accessToken, refreshToken: newRefreshToken } = generateToken(userId);
    setSession(userId, { accessToken, refreshToken: newRefreshToken });
    
    res.json({ success: true, accessToken, refreshToken: newRefreshToken });
  } catch (err) {
    res.status(401).json({ error: 'Invalid refresh token' });
  }
});

// F2: logout 使用轻量鉴权（token 无效也能正常退出）
app.post('/api/auth/logout', (req, res) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (token) {
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      if (decoded && decoded.userId) {
        deleteSession(decoded.userId);
      }
    } catch (_) {
      // token 无效也允许退出，客户端会清除本地状态
    }
  }
  res.json({ success: true });
});

app.get('/api/user/profile', authenticateToken, async (req, res) => {
  try {
    const user = db.data.users.find(u => u.id === req.user.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json({
      id: user.id,
      username: user.username,
      nickname: user.nickname,
      avatar: user.avatar,
      phone: user.phone ? '***' + user.phone.slice(-4) : null,
      role: user.role,
      metadata: user.metadata
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.put('/api/user/profile', authenticateToken, async (req, res) => {
  const { nickname, avatar } = req.body;
  
  try {
    const userIndex = db.data.users.findIndex(u => u.id === req.user.id);
    if (userIndex === -1) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    const user = db.data.users[userIndex];
    
    if (nickname) {
      user.nickname = nickname;
    }
    if (avatar) {
      user.avatar = avatar;
    }
    
    user.updated_at = new Date().toISOString();
    await db.write();
    
    res.json({
      success: true,
      user: {
        id: user.id,
        username: user.username,
        nickname: user.nickname,
        avatar: user.avatar,
        role: user.role
      }
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/user/metadata', authenticateToken, async (req, res) => {
  try {
    const user = db.data.users.find(u => u.id === req.user.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json(user.metadata);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.put('/api/user/metadata', authenticateToken, async (req, res) => {
  const { metadata } = req.body;
  
  try {
    const userIndex = db.data.users.findIndex(u => u.id === req.user.id);
    if (userIndex === -1) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    const user = db.data.users[userIndex];
    user.metadata = { ...user.metadata, ...metadata };
    user.updated_at = new Date().toISOString();
    await db.write();
    
    res.json({ success: true, metadata: user.metadata });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.use((req, res) => {
  if (req.path.startsWith('/api/')) {
    res.status(404).json({ error: 'Not found' });
  } else {
    res.status(404).send('Not found');
  }
});

// P0#2: 优雅关闭机制
let server = null;

const gracefulShutdown = async (signal) => {
  console.log(`\n${signal} received. Starting graceful shutdown...`);
  
  if (server) {
    console.log('Closing HTTP server...');
    server.close(async () => {
      console.log('HTTP server closed.');
      
      try {
        console.log('Saving database before exit...');
        await db.write();
        console.log('Database saved successfully.');
        await redisModule.closeRedis();
        console.log('Shutdown complete.');
        process.exit(0);
      } catch (err) {
        console.error('Error during shutdown:', err);
        process.exit(1);
      }
    });
    
    // 如果30秒内还没关闭，强制退出
    setTimeout(() => {
      console.error('Forced shutdown after timeout.');
      process.exit(1);
    }, 30000);
  } else {
    process.exit(0);
  }
};

process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

initDatabase().then(async () => {
  // 连接 Redis（失败不影响启动，降级到 lowdb）
  const redisOk = await redisModule.connectRedis();
  console.log(redisOk ? 'Redis: sessions & cache accelerated' : 'Redis: unavailable, using lowdb fallback');
  
  await scanVideoDirectory();
  
  setInterval(scanVideoDirectory, 300000);
  
  // F4: 每小时清理过期 sessions（先 re-read 避免并发写入冲突）
  setInterval(async () => {
    await db.read();
    cleanupSessions();
    await db.write().catch(err => console.error('Failed to save after session cleanup:', err));
  }, 3600000);
  
  server = app.listen(PORT, '0.0.0.0', () => {
  // 延长 Keep-Alive 超时，让浏览器复用 TCP 连接而非每次新建
  server.keepAliveTimeout = 65000;  // 65 秒
  server.headersTimeout = 66000;    // 略大于 keepAliveTimeout
  
    console.log(`Server running on http://0.0.0.0:${PORT}`);
    console.log(`LAN access: http://localhost:${PORT}`);
    console.log(`Video directory: ${externalVideoDir}`);
    console.log(`Cover directory: ${externalCoverDir}`);
    console.log('Poster directory: ' + externalPosterDir);
    console.log('Scanning every 5 minutes...');
  });
}).catch(err => {
  console.error('Failed to initialize database:', err);
  process.exit(1);
});
