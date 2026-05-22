import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { VideoPlayer } from '../components/VideoPlayer';
import { getDramaById, getEpisodesByDramaId, getPlayHistory, savePlayHistory, Drama, Episode } from '../services/api';

interface EpisodeWithThumbnail extends Episode {
  thumbnail?: string;
  accessed?: boolean;
}

const CACHE_CONFIG = {
  currentEpisode: { maxBuffer: 30 },
  otherEpisodes: { maxBuffer: 10 },
  maxCachedOtherEpisodes: 5,
  preloadTime: 1
};

export function PlayPage() {
  const { id } = useParams<{ id: string }>();
  const [drama, setDrama] = useState<Drama | null>(null);
  const [episodes, setEpisodes] = useState<EpisodeWithThumbnail[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [currentProgress, setCurrentProgress] = useState(0);
  const accessedEpisodesRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;

      try {
        const dramaData = await getDramaById(parseInt(id));
        setDrama(dramaData);

        const episodesData = await getEpisodesByDramaId(parseInt(id));
        let episodesWithThumbs: EpisodeWithThumbnail[] = episodesData.length > 0 
          ? episodesData.map(e => ({ ...e }))
          : createMockEpisodes(dramaData);
        
        episodesWithThumbs.sort((a, b) => (a.episode_number || a.id) - (b.episode_number || b.id));
        
        setEpisodes(episodesWithThumbs);

        const history = await getPlayHistory(parseInt(id));
        if (history && history.progress > 0) {
          setCurrentProgress(history.progress);
        }
      } catch (err) {
        console.error('Failed to fetch data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  const createMockEpisodes = (dramaData: Drama): EpisodeWithThumbnail[] => {
    const eps: EpisodeWithThumbnail[] = [];
    const baseDir = dramaData.video_url.substring(0, dramaData.video_url.lastIndexOf('/') + 1);
    
    // 从video_url中提取起始集数（例如："北派寻宝笔记/第63集.mp4" -> 63）
    const match = dramaData.video_url.match(/第(\d+)集/);
    const startEpisode = match ? parseInt(match[1]) : 1;
    
    for (let i = 1; i <= (dramaData.episode_count || 10); i++) {
      const episodeNumber = startEpisode + i - 1;
      const episodeTitle = `第${episodeNumber}集`;
      eps.push({
        id: i,
        drama_id: dramaData.id,
        title: episodeTitle,
        cover_url: dramaData.cover_url,
        video_url: `${baseDir}${episodeTitle}.mp4`,
        episode_number: i,
      });
    }
    return eps;
  };

  useEffect(() => {
    if (episodes.length === 0) return;

    const currentEpisodeId = episodes[currentIndex]?.id;
    if (currentEpisodeId) {
      accessedEpisodesRef.current.add(String(currentEpisodeId));
    }

    setEpisodes(prev => {
      let changed = false;
      const next = prev.map(ep => {
        const accessed = accessedEpisodesRef.current.has(String(ep.id));
        if (ep.accessed !== accessed) {
          changed = true;
          return { ...ep, accessed };
        }
        return ep;
      });
      return changed ? next : prev;
    });
  }, [currentIndex, episodes]);

  const handleVideoEnded = useCallback(() => {
    if (currentIndex < episodes.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setCurrentProgress(0);
    }
  }, [currentIndex, episodes.length]);

  const handleProgressChange = useCallback((progress: number) => {
    setCurrentProgress(progress);
  }, []);

  const handleSaveProgress = useCallback(() => {
    if (!id || episodes.length === 0) return;

    savePlayHistory({
      drama_id: parseInt(id),
      episode_id: episodes[currentIndex]?.id || 1,
      progress: currentProgress,
    }).catch(err => console.error('Failed to save progress:', err));
  }, [id, episodes, currentIndex, currentProgress]);

  useEffect(() => {
    const interval = setInterval(handleSaveProgress, 10000);
    return () => clearInterval(interval);
  }, [handleSaveProgress]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      handleSaveProgress();
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [handleSaveProgress]);

  const selectEpisode = (index: number) => {
    setCurrentIndex(index);
    setCurrentProgress(0);
  };

  const getVideoUrl = (videoUrl: string, maxBuffer?: number, isCurrent: boolean = true) => {
    if (videoUrl.startsWith('/api/video')) {
      const baseUrl = videoUrl.split('?')[0];
      return `${baseUrl}?maxBuffer=${maxBuffer || CACHE_CONFIG.otherEpisodes.maxBuffer}&current=${isCurrent}`;
    }
    const parts = videoUrl.split('/');
    const encodedParts = parts.map(part => encodeURIComponent(part));
    const result = `/api/video/${encodedParts.join('/')}?maxBuffer=${maxBuffer || CACHE_CONFIG.otherEpisodes.maxBuffer}&current=${isCurrent}`;
    console.log('Video URL:', videoUrl, '->', result);
    return result;
  };

  const getCoverUrl = useCallback((episode: EpisodeWithThumbnail) => {
    if (episode.poster_url) {
      const parts = episode.poster_url.split('/');
      const encodedParts = parts.map(part => encodeURIComponent(part));
      return `/posters/${encodedParts.join('/')}`;
    }
    if (episode.thumbnail) {
      return episode.thumbnail;
    }
    if (episode.cover_url) {
      if (episode.cover_url.startsWith('/covers')) {
        return episode.cover_url;
      }
      return `/covers/${encodeURIComponent(episode.cover_url)}`;
    }
    return 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><rect fill="%23333" width="160" height="90"/><text fill="%23666" font-family="sans-serif" font-size="12" x="80" y="50" text-anchor="middle">🎬</text></svg>';
  }, []);

  const currentEpisode = useMemo(() => episodes[currentIndex], [episodes, currentIndex]);

  if (loading) {
    return <div className="loading">正在获取剧集数据...</div>;
  }

  if (!drama || episodes.length === 0) {
    return <div className="loading">未找到剧集</div>;
  }

  return (
    <div className="playlist-container">
      <div className="player-section">
        <h2>{drama.title}</h2>
        <h3 className="text-lg text-gray-400 mt-2">{currentEpisode?.title}</h3>
        <VideoPlayer
          videoUrl={getVideoUrl(currentEpisode.video_url, CACHE_CONFIG.currentEpisode.maxBuffer, true)}
          poster={getCoverUrl(currentEpisode)}
          onEnded={handleVideoEnded}
          initialProgress={currentProgress}
          onProgressChange={handleProgressChange}
        />
      </div>

      <div className="playlist-section">
        <h3>剧集列表 ({episodes.length} 集)</h3>
        <div className="episode-grid">
          {episodes.map((episode, index) => (
            <div
              key={episode.id}
              className={`episode-card ${index === currentIndex ? 'active' : ''}`}
              onClick={() => selectEpisode(index)}
            >
              <img
                src={getCoverUrl(episode)}
                alt={episode.title}
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><rect fill="%23333" width="160" height="90"/><text fill="%23666" font-family="sans-serif" font-size="12" x="80" y="50" text-anchor="middle">🎬</text></svg>';
                }}
              />
              <div className="episode-info">
                <span className="episode-title">{episode.title}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
