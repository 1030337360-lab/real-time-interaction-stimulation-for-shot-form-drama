import { useState } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import { DramaList } from './components/DramaList';
import { PlayPage } from './pages/PlayPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AuthModal } from './components/AuthModal';

function AppContent() {
  const { user, logout, isAuthenticated } = useAuth();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0f0f0f]">
      <header>
        <h1 onClick={() => window.location.href = '/'} className="cursor-pointer">
          🎬 短剧播放平台
        </h1>
        <nav>
          <Link to="/">首页</Link>
          {isAuthenticated ? (
            <div className="flex items-center gap-4">
              <span className="text-gray-300">欢迎, {user?.nickname}</span>
              <button
                onClick={logout}
                className="text-[#ff4757] hover:text-[#ff3848] transition-colors"
              >
                退出登录
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsAuthModalOpen(true)}
              className="text-[#ff4757] hover:text-[#ff3848] transition-colors"
            >
              登录/注册
            </button>
          )}
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<DramaList />} />
          <Route path="/play/:id" element={<PlayPage />} />
        </Routes>
      </main>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
