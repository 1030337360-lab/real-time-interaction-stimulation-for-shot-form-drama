---
name: short-drama-player
description: "Provides comprehensive guidance for developing short drama video players using React and HLS.js. Includes video playback, progress control, fullscreen, autoplay, and playlist management features. Use when building short drama streaming applications with local LAN deployment."
license: Apache License 2.0
---

# Short Drama Video Player Skill

## When to use this skill

Use this skill whenever the user wants to:
- Create a video player component for short drama applications
- Implement video playback with HLS.js for smooth streaming
- Add play/pause, progress bar, volume control, and fullscreen features
- Build playlist management and automatic episode continuation
- Set up LAN-accessible video streaming

## How to use this skill

### Workflow

1. **Set up dependencies** - Install react, video.js or hls.js
2. **Create Player component** - Build the main video player
3. **Implement controls** - Add play/pause, progress, volume, fullscreen
4. **Add playlist support** - Enable autoplay next episode
5. **Integrate with backend** - Connect to Express video streaming API

### 1. Basic HLS Player Component

```tsx
import { useRef, useEffect, useState } from 'react';
import Hls from 'hls.js';

interface VideoPlayerProps {
  videoUrl: string;
  onEnded?: () => void;
}

export function VideoPlayer({ videoUrl, onEnded }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    if (!videoRef.current) return;

    if (Hls.isSupported()) {
      hlsRef.current = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
      });
      
      hlsRef.current.loadSource(videoUrl);
      hlsRef.current.attachMedia(videoRef.current);
      
      hlsRef.current.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('HLS manifest loaded');
      });
    } else if (videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
      videoRef.current.src = videoUrl;
    }

    return () => {
      hlsRef.current?.destroy();
    };
  }, [videoUrl]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const updateTime = () => setCurrentTime(video.currentTime);
    const updateDuration = () => setDuration(video.duration);
    const handleEnded = () => onEnded?.();
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener('timeupdate', updateTime);
    video.addEventListener('loadedmetadata', updateDuration);
    video.addEventListener('ended', handleEnded);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);

    return () => {
      video.removeEventListener('timeupdate', updateTime);
      video.removeEventListener('loadedmetadata', updateDuration);
      video.removeEventListener('ended', handleEnded);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
    };
  }, [onEnded]);

  const togglePlay = () => {
    videoRef.current?.togglePlay();
  };

  const handleProgressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    videoRef.current.currentTime = parseFloat(e.target.value);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    videoRef.current.volume = newVolume;
    setVolume(newVolume);
  };

  const toggleFullscreen = async () => {
    const container = videoRef.current?.parentElement;
    if (!container) return;

    if (!document.fullscreenElement) {
      await container.requestFullscreen();
      setIsFullscreen(true);
    } else {
      await document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="video-player-container">
      <video
        ref={videoRef}
        className="video-player"
        controls={false}
        autoPlay
        playsInline
      />
      
      <div className="controls-overlay">
        <button className="control-btn" onClick={togglePlay}>
          {isPlaying ? '⏸️' : '▶️'}
        </button>
        
        <div className="progress-container">
          <input
            type="range"
            min="0"
            max={duration || 1}
            value={currentTime}
            onChange={handleProgressChange}
            className="progress-bar"
          />
          <span className="time-display">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>
        
        <div className="volume-control">
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={volume}
            onChange={handleVolumeChange}
            className="volume-bar"
          />
        </div>
        
        <button className="control-btn" onClick={toggleFullscreen}>
          {isFullscreen ? '⛶' : '⛶'}
        </button>
      </div>
    </div>
  );
}
```

### 2. Playlist Component

```tsx
import { useState } from 'react';
import { VideoPlayer } from './VideoPlayer';

interface Episode {
  id: number;
  title: string;
  coverUrl: string;
  videoUrl: string;
}

interface PlaylistProps {
  episodes: Episode[];
  initialEpisode?: number;
}

export function PlaylistPlayer({ episodes, initialEpisode = 0 }: PlaylistProps) {
  const [currentIndex, setCurrentIndex] = useState(initialEpisode);

  const currentEpisode = episodes[currentIndex];

  const handleVideoEnded = () => {
    if (currentIndex < episodes.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const selectEpisode = (index: number) => {
    setCurrentIndex(index);
  };

  return (
    <div className="playlist-container">
      <div className="player-section">
        <VideoPlayer
          videoUrl={currentEpisode.videoUrl}
          onEnded={handleVideoEnded}
        />
        <h2>{currentEpisode.title}</h2>
      </div>
      
      <div className="playlist-section">
        <h3>剧集列表</h3>
        <div className="episode-grid">
          {episodes.map((episode, index) => (
            <div
              key={episode.id}
              className={`episode-card ${index === currentIndex ? 'active' : ''}`}
              onClick={() => selectEpisode(index)}
            >
              <img src={episode.coverUrl} alt={episode.title} />
              <span className="episode-number">第 {episode.id} 集</span>
              <span className="episode-title">{episode.title}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### 3. Video List Page

```tsx
import { useState, useEffect } from 'react';

interface Drama {
  id: number;
  title: string;
  coverUrl: string;
  description: string;
  episodeCount: number;
}

export function DramaList({ onSelectDrama }: { onSelectDrama: (drama: Drama) => void }) {
  const [dramas, setDramas] = useState<Drama[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dramas')
      .then(res => res.json())
      .then(data => {
        setDramas(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch dramas:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div className="loading">加载中...</div>;
  }

  return (
    <div className="drama-list">
      <h1>短剧列表</h1>
      <div className="drama-grid">
        {dramas.map(drama => (
          <div
            key={drama.id}
            className="drama-card"
            onClick={() => onSelectDrama(drama)}
          >
            <img src={drama.coverUrl} alt={drama.title} />
            <div className="drama-info">
              <h3>{drama.title}</h3>
              <p>{drama.description}</p>
              <span className="episode-count">{drama.episodeCount} 集</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Best Practices

- Use HLS.js for better streaming experience and seeking performance
- Handle video events properly to prevent memory leaks
- Implement responsive design for different screen sizes
- Add loading states and error handling
- Support keyboard shortcuts for accessibility
- Use React.memo for performance optimization on large playlists

## Resources

- HLS.js documentation: https://hlsjs.com/
- Video.js documentation: https://docs.videojs.com/
- Web Audio API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API

## Keywords

video player, HLS.js, React, streaming, short drama, playlist, fullscreen, volume control, progress bar