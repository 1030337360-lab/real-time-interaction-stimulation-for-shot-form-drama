import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import Hls from 'hls.js';
import { useHighlightSync } from '../hooks/useHighlightSync';
import { ReactionOverlay } from './ReactionOverlay';
import { HighlightWarning } from './HighlightWarning';

interface VideoPlayerProps {
  videoUrl: string;
  poster?: string;
  onEnded?: () => void;
  initialProgress?: number;
  onProgressChange?: (progress: number) => void;
  episodeId?: number;
}

type PlayerState = 
  | 'idle' 
  | 'loading' 
  | 'ready' 
  | 'playing' 
  | 'paused' 
  | 'buffering' 
  | 'ended' 
  | 'error';

interface PlayerError {
  code: string;
  message: string;
  recoverable: boolean;
}

export function VideoPlayer({ videoUrl, poster, onEnded, initialProgress = 0, onProgressChange, episodeId }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [playerState, setPlayerState] = useState<PlayerState>('idle');
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [bufferedRanges, setBufferedRanges] = useState<Array<{start: number; end: number}>>([]);
  const [error, setError] = useState<PlayerError | null>(null);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [displayTime, setDisplayTime] = useState(0);
  const [userWantsToPlay, setUserWantsToPlay] = useState(false);
  const [showVolume, setShowVolume] = useState(false);
  const [highlights, setHighlights] = useState<number[]>([]);
  const [animationEnabled, setAnimationEnabled] = useState(() => {
    const stored = localStorage.getItem('highlightAnimationEnabled');
    return stored === null ? true : stored === 'true';
  });

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  const highlightState = useHighlightSync(
    highlights,
    displayTime,
    duration,
    playerState === 'paused',
    { enabled: animationEnabled && highlights.length > 0 }
  );
  
  const currentTimeRef = useRef(0);
  const durationRef = useRef(0);
  const idleTimerRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const playerStateRef = useRef<PlayerState>('idle');
  const wasPlayingBeforeDragRef = useRef(false);
  
  const formatTime = useCallback((time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  const updateBufferedRanges = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.buffered.length === 0) {
      setBufferedRanges([]);
      return;
    }

    const ranges: Array<{start: number; end: number}> = [];
    const maxBuffer = currentTimeRef.current + 30;
    
    for (let i = 0; i < video.buffered.length; i++) {
      const start = video.buffered.start(i);
      const end = Math.min(video.buffered.end(i), maxBuffer);
      if (end > start) {
        ranges.push({ start, end });
      }
    }
    
    setBufferedRanges(ranges);
  }, []);

  const updateTimeDisplay = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    
    animationFrameRef.current = requestAnimationFrame(() => {
      if (!isDragging) {
        const time = currentTimeRef.current;
        setDisplayTime(time);
      }
      
      if (playerStateRef.current === 'playing') {
        updateTimeDisplay();
      }
    });
  }, [isDragging]);

  const handleStateTransition = useCallback((newState: PlayerState) => {
    console.log(`Player state: ${playerStateRef.current} -> ${newState}`);
    setPlayerState(newState);
    playerStateRef.current = newState;
    
    if (newState === 'playing') {
      updateTimeDisplay();
    } else if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  }, [updateTimeDisplay]);

  const handlePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    if (playerStateRef.current === 'loading' || playerStateRef.current === 'buffering') {
      setUserWantsToPlay(true);
      return;
    }

    if (playerStateRef.current === 'error') {
      handleRetry();
      return;
    }

    video.play().then(() => {
      handleStateTransition('playing');
    }).catch((err) => {
      console.error('Play failed:', err);
      setError({
        code: 'PLAY_FAILED',
        message: '播放失败，请重试',
        recoverable: true,
      });
      handleStateTransition('error');
    });
  }, [handleStateTransition]);

  const handlePause = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    
    video.pause();
    handleStateTransition('paused');
  }, [handleStateTransition]);

  const togglePlay = useCallback(() => {
    if (playerStateRef.current === 'playing') {
      handlePause();
    } else {
      handlePlay();
    }
  }, [handlePlay, handlePause]);

  const handleEnded = useCallback(() => {
    handleStateTransition('ended');
    onEnded?.();
  }, [handleStateTransition, onEnded]);

  const handleProgressChangeStart = useCallback(() => {
    wasPlayingBeforeDragRef.current = playerStateRef.current === 'playing';
    setIsDragging(true);
  }, []);

  const handleProgressChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    setDisplayTime(newTime);
  }, []);

  const handleProgressChangeEnd = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    try {
      video.currentTime = displayTime;
      setIsDragging(false);

      if (wasPlayingBeforeDragRef.current) {
        video.play().then(() => {
          handleStateTransition('playing');
        }).catch((err) => {
          console.error('Resume playback after seek failed:', err);
        });
      }
    } catch (err) {
      console.error('Seek failed:', err);
      setIsDragging(false);
    }
  }, [displayTime, handleStateTransition]);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    const video = videoRef.current;
    if (video) {
      video.volume = newVolume;
    }
    setVolume(newVolume);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    const container = containerRef.current;
    if (!container) return;

    try {
      if (!document.fullscreenElement) {
        if (container.requestFullscreen) {
          await container.requestFullscreen();
        } else if ((container as any).webkitRequestFullscreen) {
          await (container as any).webkitRequestFullscreen();
        } else if ((container as any).mozRequestFullScreen) {
          await (container as any).mozRequestFullScreen();
        } else if ((container as any).msRequestFullscreen) {
          await (container as any).msRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen();
        } else if ((document as any).mozCancelFullScreen) {
          await (document as any).mozCancelFullScreen();
        } else if ((document as any).msExitFullscreen) {
          await (document as any).msExitFullscreen();
        }
      }
    } catch (err) {
      console.error('Fullscreen operation failed:', err);
    }
  }, []);

  const toggleAnimation = useCallback(() => {
    setAnimationEnabled((prev) => {
      const newValue = !prev;
      localStorage.setItem('highlightAnimationEnabled', String(newValue));
      return newValue;
    });
  }, []);

  const handleRetry = useCallback(() => {
    setError(null);
    handleStateTransition('loading');
    
    const video = videoRef.current;
    if (!video) return;

    if (hlsRef.current) {
      hlsRef.current.recoverMediaError();
    } else {
      video.load();
    }
  }, [handleStateTransition]);

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
    }
    
    setControlsVisible(true);
    
    idleTimerRef.current = window.setTimeout(() => {
      if (playerStateRef.current === 'playing') {
        setControlsVisible(false);
      }
    }, 3000);
  }, []);

  useEffect(() => {
    resetIdleTimer();
  }, [resetIdleTimer]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      durationRef.current = video.duration;
      setDuration(video.duration);
      
      if (initialProgress > 0 && !isNaN(video.duration)) {
        video.currentTime = Math.min(initialProgress, video.duration);
        currentTimeRef.current = video.currentTime;
        setDisplayTime(video.currentTime);
      }
      
      handleStateTransition('ready');
      
      if (userWantsToPlay) {
        video.play().then(() => {
          handleStateTransition('playing');
          setUserWantsToPlay(false);
        }).catch((err) => {
          console.error('Auto play failed:', err);
          setUserWantsToPlay(false);
        });
      }
    };

    const handleTimeUpdate = () => {
      currentTimeRef.current = video.currentTime;
      if (!isDragging) {
        setDisplayTime(video.currentTime);
      }
      onProgressChange?.(video.currentTime);
    };

    const handleWaiting = () => {
      if (playerStateRef.current === 'playing') {
        handleStateTransition('buffering');
      }
    };

    const handleCanPlay = () => {
      if (playerStateRef.current === 'buffering') {
        handleStateTransition('ready');
        
        if (userWantsToPlay) {
          video.play().then(() => {
            handleStateTransition('playing');
            setUserWantsToPlay(false);
          }).catch((err) => {
            console.error('Auto play failed:', err);
            setUserWantsToPlay(false);
          });
        }
      }
    };

    const handlePlayEvent = () => {
      if (playerStateRef.current !== 'playing') {
        handleStateTransition('playing');
      }
    };

    const handlePauseEvent = () => {
      if (playerStateRef.current !== 'paused' && playerStateRef.current !== 'ended') {
        handleStateTransition('paused');
      }
    };

    const handleProgress = () => {
      updateBufferedRanges();
    };

    const handleStalled = () => {
      console.warn('Video stalled, attempting recovery');
      if (hlsRef.current) {
        hlsRef.current.recoverMediaError();
      }
    };

    const handleSuspend = () => {
      console.warn('Video suspended');
    };

    const handleError = (e: Event) => {
      console.error('Video error:', e);
      setError({
        code: 'VIDEO_ERROR',
        message: '视频播放出错',
        recoverable: true,
      });
      handleStateTransition('error');
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('waiting', handleWaiting);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('play', handlePlayEvent);
    video.addEventListener('pause', handlePauseEvent);
    video.addEventListener('progress', handleProgress);
    video.addEventListener('stalled', handleStalled);
    video.addEventListener('suspend', handleSuspend);
    video.addEventListener('error', handleError);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('waiting', handleWaiting);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('play', handlePlayEvent);
      video.removeEventListener('pause', handlePauseEvent);
      video.removeEventListener('progress', handleProgress);
      video.removeEventListener('stalled', handleStalled);
      video.removeEventListener('suspend', handleSuspend);
      video.removeEventListener('error', handleError);
      video.removeEventListener('ended', handleEnded);
    };
  }, [videoUrl, initialProgress, onProgressChange, handleStateTransition, updateBufferedRanges, handleEnded, userWantsToPlay, isDragging]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const isFull = !!document.fullscreenElement;
      setIsFullscreen(isFull);
      
      if (isFull) {
        setControlsVisible(true);
        resetIdleTimer();
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, [resetIdleTimer]);

  useEffect(() => {
    if (!videoRef.current) return;

    const video = videoRef.current;
    setError(null);
    handleStateTransition('loading');

    const isHls = videoUrl.toLowerCase().endsWith('.m3u8');

    if (isHls && Hls.isSupported()) {
      hlsRef.current = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
      });

      hlsRef.current.loadSource(videoUrl);
      hlsRef.current.attachMedia(video);

      hlsRef.current.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('HLS manifest parsed');
      });

      hlsRef.current.on(Hls.Events.ERROR, (_event, data) => {
        console.error('HLS error:', data);
        
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              console.log('Network error, trying to recover');
              hlsRef.current?.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              console.log('Media error, trying to recover');
              hlsRef.current?.recoverMediaError();
              break;
            default:
              console.error('Fatal error, cannot recover');
              setError({
                code: 'HLS_FATAL',
                message: '视频加载失败，请刷新页面重试',
                recoverable: true,
              });
              handleStateTransition('error');
              break;
          }
        }
      });
    } else {
      video.src = videoUrl;
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      } else {
        video.pause();
        video.removeAttribute('src');
      }
      
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current);
      }
      
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [videoUrl]);

  useEffect(() => {
    const fetchHighlights = async () => {
      if (!episodeId) {
        setHighlights([]);
        return;
      }
      
      try {
        const response = await fetch(`/api/episodes/${episodeId}/highlights`);
        if (response.ok) {
          const points = await response.json();
          setHighlights(points);
        } else {
          setHighlights([]);
        }
      } catch (err) {
        console.error('Failed to fetch highlights:', err);
        setHighlights([]);
      }
    };
    
    fetchHighlights();
  }, [episodeId]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !video.src) return;

    if (
      initialProgress > 0 &&
      Math.abs(video.currentTime - initialProgress) > 2
    ) {
      video.currentTime = initialProgress;
      currentTimeRef.current = initialProgress;
      setDisplayTime(initialProgress);
    }
  }, [initialProgress]);

  useEffect(() => {
    setDisplayTime(0);
    setDuration(0);
    setBufferedRanges([]);
    currentTimeRef.current = 0;
    durationRef.current = 0;
  }, [videoUrl]);

  const progressBarRef = useRef<HTMLInputElement>(null);
  const progressPercent = duration > 0 ? (displayTime / duration) * 100 : 0;

  const glowIntensity = useMemo(() => {
    if (highlights.length === 0 || duration <= 0) return 0;
    const currentTimeSeconds = displayTime;
    const upcoming = highlights
      .map((p) => (p / 100) * duration)
      .filter((t) => t > currentTimeSeconds)
      .sort((a, b) => a - b);
    if (upcoming.length === 0) return 0;
    const nearest = upcoming[0];
    const timeToNext = nearest - currentTimeSeconds;
    if (timeToNext > 5) return 0;
    if (timeToNext <= 0) return 1;
    return 1 - timeToNext / 5;
  }, [highlights, displayTime, duration]);

  const showProgressGlow = glowIntensity > 0;

  return (
    <div 
      ref={containerRef}
      className="video-player-container"
      onMouseMove={resetIdleTimer}
      onMouseEnter={() => setControlsVisible(true)}
      onClick={() => {
        setShowVolume(false);
        if (playerState === 'playing' || playerState === 'paused') {
          togglePlay();
        }
      }}
    >
      <video
        ref={videoRef}
        className="video-player"
        controls={false}
        autoPlay={false}
        playsInline
        poster={poster}
        preload="auto"
      />

      {playerState === 'ready' && (
        <div 
          className="center-play-btn"
          onClick={(e) => {
            e.stopPropagation();
            handlePlay();
          }}
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
        </div>
      )}

      {playerState === 'loading' && (
        <div className="center-loading">
          <div className="loading-spinner" />
        </div>
      )}

      {playerState === 'buffering' && (
        <div className="center-loading center-buffering">
          <div className="loading-spinner loading-spinner-small" />
        </div>
      )}

      {error && (
        <div className="center-error">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          <p>{error.message}</p>
          {error.recoverable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRetry();
              }}
            >
              点击重试
            </button>
          )}
        </div>
      )}

      {console.log('[VideoPlayer render] highlights.length=%d phase=%s', highlights.length, highlightState.phase)}
      <ReactionOverlay
        phase={highlightState.phase}
        timeToNext={highlightState.timeToNext}
        highlights={highlights}
        isMobile={isMobile}
      />

      <button
        className={`animation-toggle${!animationEnabled ? ' disabled' : ''}`}
        onClick={(e) => {
          e.stopPropagation();
          toggleAnimation();
        }}
        title={animationEnabled ? '关闭高光动画' : '开启高光动画'}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
          <path d="M12 3l2.5 5.5L20 9l-4 3.8L17 19l-5-2.7L7 19l1-6.2L4 9l5.5-.5z"/>
          {!animationEnabled && <line x1="3" y1="3" x2="21" y2="21" />}
        </svg>
      </button>

      <div
        className={`controls-bar ${controlsVisible ? 'visible' : ''}`}
        onMouseMove={resetIdleTimer}
        onClick={(e) => e.stopPropagation()}
      >
        <button className="btn-play" onClick={togglePlay}>
          {playerState === 'playing' ? (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>

        <div className="progress-area">
          <div
            className={`progress-track ${showProgressGlow ? 'highlight-near' : ''}`}
            style={{
              '--glow-intensity': glowIntensity,
            } as React.CSSProperties}
          >
            {bufferedRanges.map((range, index) => (
              <div
                key={index}
                className="progress-buffer"
                style={{
                  left: `${(range.start / duration) * 100}%`,
                  width: `${((range.end - range.start) / duration) * 100}%`,
                }}
              />
            ))}
            <div
              className="progress-played"
              style={{ width: `${progressPercent}%` }}
            />
            <HighlightWarning
              highlights={highlights}
              currentTime={displayTime}
              duration={duration}
            />
            <div
              className="progress-thumb"
              style={{ left: `${progressPercent}%` }}
            />
            <input
              ref={progressBarRef}
              type="range"
              min="0"
              max={duration > 0 ? duration : 1}
              value={displayTime}
              onMouseDown={handleProgressChangeStart}
              onChange={handleProgressChange}
              onMouseUp={handleProgressChangeEnd}
              onTouchStart={handleProgressChangeStart}
              onTouchEnd={handleProgressChangeEnd}
              className="progress-bar-input"
              disabled={playerState === 'error'}
            />
          </div>
          <span className="time-text">
            {formatTime(displayTime)} / {duration > 0 ? formatTime(duration) : '--:--'}
          </span>
        </div>

        <div 
          className="volume-box"
          onMouseLeave={() => setShowVolume(false)}
        >
          <button 
            className="volume-btn"
            onClick={(e) => {
              e.stopPropagation();
              setShowVolume(!showVolume);
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              {volume === 0 ? (
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-3.97zM14 3.23v2.06c2.89 1.27 5 4.12 5 7.71s-2.11 6.44-5 7.71v2.06c4.01-1.29 7-4.95 7-9.77s-2.99-8.48-7-9.77zM3 9v6h4l5 5V4L7 9H3z"/>
              ) : volume < 0.5 ? (
                <path d="M7 9v6h4l5 5V4l-5 5H7z"/>
              ) : (
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-3.97zM14 3.23v2.06c2.89 1.27 5 4.12 5 7.71s-2.11 6.44-5 7.71v2.06c4.01-1.29 7-4.95 7-9.77s-2.99-8.48-7-9.77z"/>
              )}
            </svg>
          </button>
          {showVolume && (
            <div 
              className="volume-popup"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="volume-track">
                <div 
                  className="volume-fill" 
                  style={{ height: `${volume * 100}%` }}
                />
                <div 
                  className="volume-thumb"
                  style={{ bottom: `${volume * 100}%` }}
                />
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="volume-input"
                  autoFocus
                />
              </div>
            </div>
          )}
        </div>

        <button className="btn-fullscreen" onClick={toggleFullscreen}>
          {isFullscreen ? (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
