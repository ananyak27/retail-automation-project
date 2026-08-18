import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import ChatBot from './components/ChatBot';
import OwnerDashboard from './components/OwnerDashboard';
import { ShoppingCart } from 'lucide-react';

const BACKEND_URL = "http://127.0.0.1:8000";

export default function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    // Read session on startup
    const stored = localStorage.getItem('retail_session');
    if (stored) {
      try {
        setSession(JSON.parse(stored));
      } catch (e) {
        localStorage.removeItem('retail_session');
      }
    }
  }, []);

  const handleLoginSuccess = (userSession) => {
    setSession(userSession);
  };

  const handleLogout = () => {
    localStorage.removeItem('retail_session');
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
