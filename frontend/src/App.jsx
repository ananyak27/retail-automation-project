import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import ChatBot from './components/ChatBot';
import OwnerDashboard from './components/OwnerDashboard';
import { ShoppingCart } from 'lucide-react';

const getBackendUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  const hostname = window.location.hostname;
  if (!hostname || hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://192.168.1.105:8000';
  }
  return `http://${hostname}:8000`;
};

const BACKEND_URL = getBackendUrl();

export const getWebSocketUrl = (backendUrl, userId) => {
  const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
  const host = backendUrl.replace(/^https?:\/\//, '');
  return `${wsProtocol}//${host}/ws/${userId}`;
};

export default function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    // Read session on startup from sessionStorage for tab isolation
    const stored = sessionStorage.getItem('retail_session');
    if (stored) {
      try {
        setSession(JSON.parse(stored));
      } catch (e) {
        sessionStorage.removeItem('retail_session');
      }
    }
  }, []);

  const handleLoginSuccess = (userSession) => {
    sessionStorage.setItem('retail_session', JSON.stringify(userSession));
    setSession(userSession);
  };

  const handleLogout = () => {
    sessionStorage.removeItem('retail_session');
    setSession(null);
  };

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="app-header">
        <div className="logo">
          <ShoppingCart size={24} />
          <span>Retail<span>Automate</span></span>
        </div>
        
        {session && (
          <div className="user-nav">
            <div className="user-badge">
              {session.role === 'owner' ? '🏪 Shop Owner' : '👨‍💼 Customer'}
              <span style={{ fontSize: '11px', opacity: 0.8, marginLeft: '4px' }}>
                ({session.phone_number})
              </span>
            </div>
            <button className="btn-logout" onClick={handleLogout}>
              Logout
            </button>
          </div>
        )}
      </header>

      {/* Main Panel Content */}
      <main className="main-content">
        {!session ? (
          <Login onLoginSuccess={handleLoginSuccess} backendUrl={BACKEND_URL} />
        ) : session.role === 'owner' ? (
          <OwnerDashboard session={session} backendUrl={BACKEND_URL} />
        ) : (
          <ChatBot session={session} backendUrl={BACKEND_URL} />
        )}
      </main>
    </div>
  );
}
