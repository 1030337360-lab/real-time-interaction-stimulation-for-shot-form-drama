---
name: short-drama-init
description: "Provides guidance for initializing a short drama video streaming project. Includes project structure setup, frontend React app, backend Express server, database configuration, and LAN deployment. Use when starting a new short drama project from scratch."
license: Apache License 2.0
---

# Short Drama Project Initialization Skill

## When to use this skill

Use this skill whenever the user wants to:
- Initialize a new short drama streaming project
- Set up project structure with frontend and backend
- Configure Express server for video streaming
- Set up SQLite database for drama metadata
- Prepare LAN-accessible deployment configuration

## How to use this skill

### Workflow

1. **Create project directory structure**
2. **Initialize frontend React + Vite project**
3. **Set up Express backend server**
4. **Configure SQLite database**
5. **Add video streaming endpoints**
6. **Configure LAN deployment**

### 1. Project Structure

```
short-drama-project/
├── client/                    # React frontend
│   ├── src/
│   │   ├── components/       # VideoPlayer, DramaList, etc.
│   │   ├── pages/            # Home, Player, etc.
│   │   ├── services/         # API calls
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── server/                    # Express backend
│   ├── routes/               # API routes
│   ├── controllers/          # Request handlers
│   ├── database/             # SQLite setup
│   ├── videos/               # Video files storage
│   ├── covers/               # Cover images
│   ├── app.js
│   └── package.json
│
└── README.md
```

### 2. Initialize Frontend

```bash
# Create Vite + React + TypeScript project
npm create vite@6.5.0 . -- --template react-ts

# Install dependencies
npm install
npm install hls.js axios react-router-dom

# Install dev dependencies
npm install -D tailwindcss @tailwindcss/vite
```

### 3. Vite Configuration (vite.config.ts)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
});
```

### 4. Initialize Backend

```bash
mkdir server && cd server
npm init -y

# Install dependencies
npm install express cors helmet sqlite3 path fs-extra
npm install -D @types/node @types/express @types/cors @types/helmet
```

### 5. Express Server (app.js)

```javascript
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const videoDir = path.join(__dirname, 'videos');
const coverDir = path.join(__dirname, 'covers');

if (!fs.existsSync(videoDir)) fs.mkdirSync(videoDir, { recursive: true });
if (!fs.existsSync(coverDir)) fs.mkdirSync(coverDir, { recursive: true });

const sqlite3 = require('sqlite3').verbose();
const dbPath = path.join(__dirname, 'database', 'drama.db');

if (!fs.existsSync(path.dirname(dbPath))) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
}

const db = new sqlite3.Database(dbPath, (err) => {
  if (err) console.error('Database connection error:', err);
  else {
    db.run(`
      CREATE TABLE IF NOT EXISTS dramas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        cover_url TEXT,
        video_url TEXT,
        episode_count INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    db.run(`
      CREATE TABLE IF NOT EXISTS play_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drama_id INTEGER,
        episode_id INTEGER DEFAULT 1,
        progress INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (drama_id) REFERENCES dramas(id)
      )
    `);
  }
});

app.get('/api/dramas', (req, res) => {
  db.all('SELECT * FROM dramas', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

app.get('/api/dramas/:id', (req, res) => {
  const { id } = req.params;
  db.get('SELECT * FROM dramas WHERE id = ?', [id], (err, row) => {
    if (err) return res.status(500).json({ error: err.message });
    if (!row) return res.status(404).json({ error: 'Drama not found' });
    res.json(row);
  });
});

app.get('/api/video/:filename', (req, res) => {
  const { filename } = req.params;
  const filePath = path.join(videoDir, filename);
  
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Video not found' });
  }

  const stat = fs.statSync(filePath);
  const fileSize = stat.size;
  const range = req.headers.range;

  if (range) {
    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    const chunksize = end - start + 1;
    const file = fs.createReadStream(filePath, { start, end });
    const head = {
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunksize,
      'Content-Type': 'video/mp4',
    };
    res.writeHead(206, head);
    file.pipe(res);
  } else {
    const head = {
      'Content-Length': fileSize,
      'Content-Type': 'video/mp4',
    };
    res.writeHead(200, head);
    fs.createReadStream(filePath).pipe(res);
  }
});

app.post('/api/history', (req, res) => {
  const { drama_id, episode_id, progress } = req.body;
  db.run(
    'INSERT OR REPLACE INTO play_history (drama_id, episode_id, progress) VALUES (?, ?, ?)',
    [drama_id, episode_id, progress],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ id: this.lastID });
    }
  );
});

app.get('/api/history/:drama_id', (req, res) => {
  const { drama_id } = req.params;
  db.get(
    'SELECT * FROM play_history WHERE drama_id = ?',
    [drama_id],
    (err, row) => {
      if (err) return res.status(500).json({ error: err.message });
      res.json(row || { progress: 0 });
    }
  );
});

app.get('/covers/:filename', (req, res) => {
  const { filename } = req.params;
  const filePath = path.join(coverDir, filename);
  
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Cover not found' });
  }
  
  res.sendFile(filePath);
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on http://0.0.0.0:${PORT}`);
  console.log(`LAN access: http://localhost:${PORT}`);
});
```

### 6. Sample Drama Data

```javascript
// Add sample data
db.run(`
  INSERT INTO dramas (title, description, cover_url, video_url, episode_count)
  VALUES (
    '短剧示例',
    '这是一个精彩的短剧示例',
    '/covers/sample.jpg',
    '/api/video/sample.mp4',
    10
  )
`);
```

### 7. LAN Deployment

```bash
# Get local IP address (Windows)
ipconfig | findstr IPv4

# Get local IP address (Linux/Mac)
ifconfig | grep inet

# Start backend
cd server && node app.js

# Start frontend (in separate terminal)
cd client && npm run dev
```

## Best Practices

- Keep video files in a dedicated directory with proper permissions
- Use Range requests for video streaming to support seeking
- Configure CORS properly for development and production
- Use environment variables for configuration
- Add error handling for all API endpoints
- Implement graceful shutdown for the server

## Resources

- Express documentation: https://expressjs.com/
- SQLite documentation: https://www.sqlite.org/docs.html
- Vite documentation: https://vitejs.dev/

## Keywords

project initialization, short drama, video streaming, Express, React, SQLite, LAN deployment, project structure