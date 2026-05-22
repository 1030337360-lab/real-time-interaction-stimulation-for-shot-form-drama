import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDramas, Drama } from '../services/api';

export function DramaList() {
  const [dramas, setDramas] = useState<Drama[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const navigate = useNavigate();

  const fetchDramas = async (isRefresh = false) => {
    if (!isRefresh) setLoading(true);
    try {
      const data = await getDramas();
      setDramas(data);
      console.log('Fetched dramas from server:', data.length);
    } catch (err) {
      console.error('Failed to fetch dramas:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDramas();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      console.log('Refreshing drama list...');
      fetchDramas(true);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const handleSelectDrama = (drama: Drama) => {
    navigate(`/play/${drama.id}`);
  };

  const getCoverUrl = (coverUrl: string | undefined) => {
    if (!coverUrl) {
      return 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150"><rect fill="%23333" width="200" height="150"/><text fill="%23666" font-family="sans-serif" font-size="14" x="100" y="80" text-anchor="middle">No Cover</text></svg>';
    }
    return `/covers/${encodeURIComponent(coverUrl)}`;
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDramas(true);
  };

  if (loading) {
    return <div className="loading">正在获取剧集数据...</div>;
  }

  return (
    <div className="drama-list">
      <div className="flex items-center justify-between px-6 py-4">
        <h2 className="text-xl font-bold">短剧列表</h2>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
        >
          {refreshing ? '刷新中...' : '刷新列表'}
        </button>
      </div>
      <div className="drama-grid">
        {dramas.map(drama => (
          <div
            key={drama.id}
            className="drama-card"
            onClick={() => handleSelectDrama(drama)}
          >
            <img
              src={getCoverUrl(drama.cover_url)}
              alt={drama.title}
              onError={(e) => {
                (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150"><rect fill="%23333" width="200" height="150"/><text fill="%23666" font-family="sans-serif" font-size="14" x="100" y="80" text-anchor="middle">No Cover</text></svg>';
              }}
            />
            <div className="drama-info">
              <h3>{drama.title}</h3>
              <p>{drama.description}</p>
              <span className="episode-count">{drama.episode_count} 集</span>
            </div>
          </div>
        ))}
      </div>
      {dramas.length === 0 && (
        <div className="loading">暂无剧集，请将视频文件放入 D:\video_data 目录</div>
      )}
    </div>
  );
}
