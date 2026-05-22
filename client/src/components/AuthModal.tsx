import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!username || !password) {
      setError('请填写用户名和密码');
      return;
    }
    
    if (!isLogin && password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    
    setLoading(true);
    
    try {
      if (isLogin) {
        await login(username, password);
      } else {
        await register(username, password, phone || undefined);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed top-0 left-0 right-0 bottom-0 z-50" 
      onClick={onClose}
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '16px',
      }}
    >
      <div 
        className="bg-[#1a1a1a] rounded-xl shadow-2xl"
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '400px',
          padding: '32px',
          position: 'relative',
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">
            {isLogin ? '登录' : '注册'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-gray-300 text-sm mb-2">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-4 py-3 bg-[#242424] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-[#ff4757] transition-colors"
              placeholder="请输入用户名"
              disabled={loading}
            />
          </div>

          {!isLogin && (
            <div>
              <label className="block text-gray-300 text-sm mb-2">手机号（选填）</label>
              <input
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                className="w-full px-4 py-3 bg-[#242424] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-[#ff4757] transition-colors"
                placeholder="请输入手机号"
                disabled={loading}
              />
            </div>
          )}

          <div>
            <label className="block text-gray-300 text-sm mb-2">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-[#242424] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-[#ff4757] transition-colors"
              placeholder="请输入密码"
              disabled={loading}
            />
          </div>

          {!isLogin && (
            <div>
              <label className="block text-gray-300 text-sm mb-2">确认密码</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-3 bg-[#242424] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-[#ff4757] transition-colors"
                placeholder="请再次输入密码"
                disabled={loading}
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#ff4757] hover:bg-[#ff3848] text-white font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '加载中...' : (isLogin ? '登录' : '注册')}
          </button>
        </form>

        <div className="mt-6 text-center">
          <span className="text-gray-400 text-sm">
            {isLogin ? '还没有账号？' : '已有账号？'}
          </span>
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
            className="ml-2 text-[#ff4757] hover:text-[#ff3848] text-sm font-semibold transition-colors"
          >
            {isLogin ? '立即注册' : '立即登录'}
          </button>
        </div>
      </div>
    </div>
  );
}
