import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

export interface User {
  id: number;
  username: string;
  nickname: string;
  avatar: string | null;
  role: string;
}

export interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, phone?: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    const storedAccessToken = localStorage.getItem('accessToken');
    const storedRefreshToken = localStorage.getItem('refreshToken');
    
    if (storedUser && storedAccessToken) {
      setUser(JSON.parse(storedUser));
      setAccessToken(storedAccessToken);
      setRefreshToken(storedRefreshToken || null);
    }
  }, []);

  useEffect(() => {
    if (refreshToken) {
      const interval = setInterval(async () => {
        try {
          await refreshTokenFn();
        } catch (err) {
          console.error('Failed to refresh token:', err);
        }
      }, 60 * 60 * 1000);

      return () => clearInterval(interval);
    }
  }, [refreshToken]);

  const refreshTokenFn = useCallback(async () => {
    if (!refreshToken) return;
    
    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refreshToken }),
      });
      
      if (response.ok) {
        const data = await response.json();
        setAccessToken(data.accessToken);
        setRefreshToken(data.refreshToken);
        localStorage.setItem('accessToken', data.accessToken);
        localStorage.setItem('refreshToken', data.refreshToken);
      }
    } catch (err) {
      console.error('Token refresh failed:', err);
      logout();
    }
  }, [refreshToken]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Login failed');
    }
    
    const data = await response.json();
    setUser(data.user);
    setAccessToken(data.accessToken);
    setRefreshToken(data.refreshToken);
    
    localStorage.setItem('user', JSON.stringify(data.user));
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
  }, []);

  const register = useCallback(async (username: string, password: string, phone?: string) => {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password, phone }),
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Registration failed');
    }
    
    const data = await response.json();
    setUser(data.user);
    setAccessToken(data.accessToken);
    setRefreshToken(data.refreshToken);
    
    localStorage.setItem('user', JSON.stringify(data.user));
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
  }, []);

  const logout = useCallback(() => {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    }).catch(console.error);
    
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);
    
    localStorage.removeItem('user');
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
  }, [accessToken]);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        login,
        register,
        logout,
        refreshToken: refreshTokenFn,
        isAuthenticated: !!user && !!accessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
