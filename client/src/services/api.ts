import axios from 'axios';

export interface Drama {
  id: number;
  title: string;
  description: string;
  cover_url: string;
  video_url: string;
  episode_count: number;
  created_at: string;
}

export interface Episode {
  id: number;
  drama_id: number;
  title: string;
  cover_url: string;
  video_url: string;
  episode_number: number;
  poster_url?: string;
}

export interface PlayHistory {
  id: number;
  drama_id: number;
  episode_id: number;
  progress: number;
  updated_at: string;
}

export interface User {
  id: number;
  username: string;
  nickname: string;
  avatar: string | null;
  role: string;
  phone?: string;
  metadata?: UserMetadata;
}

export interface UserMetadata {
  watch_count: number;
  favorite_count: number;
  last_login: string | null;
  created_at: string;
  preferences: Record<string, any>;
}

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

api.interceptors.request.use((config) => {
  const accessToken = localStorage.getItem('accessToken');
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// F3: 401 自动刷新 token，失败才清除登录状态
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // 已有刷新进行中，排队等待
        return new Promise((resolve) => {
          addRefreshSubscriber((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      const refreshToken = localStorage.getItem('refreshToken');
      if (refreshToken) {
        try {
          const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refreshToken }),
          });
          
          if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.accessToken);
            localStorage.setItem('refreshToken', data.refreshToken);
            
            api.defaults.headers.common.Authorization = `Bearer ${data.accessToken}`;
            originalRequest.headers.Authorization = `Bearer ${data.accessToken}`;
            
            isRefreshing = false;
            onRefreshed(data.accessToken);
            
            return api(originalRequest);
          }
        } catch (_) {
          // refresh 失败，清除状态
        }
      }
      
      // 刷新失败，清除登录状态
      isRefreshing = false;
      refreshSubscribers = [];
      localStorage.removeItem('user');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      // 派发事件让 AuthContext 感知
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
    return Promise.reject(error);
  }
);

export async function getDramas(): Promise<Drama[]> {
  const response = await api.get('/dramas');
  return response.data;
}

export async function getDramaById(id: number): Promise<Drama> {
  const response = await api.get(`/dramas/${id}`);
  return response.data;
}

export async function getEpisodesByDramaId(dramaId: number): Promise<Episode[]> {
  const response = await api.get(`/episodes/${dramaId}`);
  return response.data;
}

export async function getPlayHistory(dramaId: number): Promise<PlayHistory> {
  const response = await api.get(`/history/${dramaId}`);
  return response.data;
}

export async function savePlayHistory(data: {
  drama_id: number;
  episode_id: number;
  progress: number;
}): Promise<{ id: number }> {
  const response = await api.post('/history', data);
  return response.data;
}

export async function saveEpisodePoster(episodeId: number, poster_url: string): Promise<{ success: boolean }> {
  const response = await api.post(`/episodes/${episodeId}/poster`, { poster_url });
  return response.data;
}

export async function getCacheStatus(): Promise<any> {
  const response = await api.get('/cache/status');
  return response.data;
}

export async function clearCache(episodeKeys?: string[]): Promise<{ message: string }> {
  const response = await api.post('/cache/clear', { episodeKeys });
  return response.data;
}

export async function getHighlights(episodeId: number): Promise<number[]> {
  const response = await api.get(`/episodes/${episodeId}/highlights`);
  return response.data;
}

export async function getUserProfile(): Promise<User> {
  const response = await api.get('/user/profile');
  return response.data;
}

export async function updateUserProfile(data: {
  nickname?: string;
  avatar?: string;
}): Promise<User> {
  const response = await api.put('/user/profile', data);
  return response.data.user;
}

export async function getUserMetadata(): Promise<UserMetadata> {
  const response = await api.get('/user/metadata');
  return response.data;
}

export async function updateUserMetadata(metadata: Partial<UserMetadata>): Promise<UserMetadata> {
  const response = await api.put('/user/metadata', { metadata });
  return response.data.metadata;
}

export default api;
