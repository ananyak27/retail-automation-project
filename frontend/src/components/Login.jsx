import React, { useState, useEffect } from 'react';
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { ShieldCheck, Phone, Key, HelpCircle, Store } from 'lucide-react';
import OwnerRegister from './OwnerRegister';

export default function Login({ onLoginSuccess, backendUrl }) {
  const [isRegisteringOwner, setIsRegisteringOwner] = useState(false);
  const [role, setRole] = useState('customer'); // 'customer' or 'owner'
  const [phoneNumber, setPhoneNumber] = useState('');
  const [otp, setOtp] = useState('');
  const [verificationId, setVerificationId] = useState(null);
  const [confirmationResult, setConfirmationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMsg, setInfoMsg] = useState('');
  const [showBypass, setShowBypass] = useState(true);

  useEffect(() => {
    // Only initialize Recaptcha if we are in real Firebase Auth mode
    if (!verificationId && !confirmationResult && !isRegisteringOwner) {
      try {
        const container = document.getElementById('recaptcha-container');
        if (container) {
          window.recaptchaVerifier = new RecaptchaVerifier(auth, container, {
            size: 'invisible',
            callback: (response) => {
              // reCAPTCHA solved
            }
          });
        }
      } catch (err) {
        console.warn("Firebase reCAPTCHA initialization failed. Local Bypass will be used.", err);
      }
    }
  }, [isRegisteringOwner, verificationId, confirmationResult]);

  if (isRegisteringOwner) {
    return (
      <OwnerRegister
        onLoginSuccess={onLoginSuccess}
        onBackToLogin={() => setIsRegisteringOwner(false)}
        backendUrl={backendUrl}
      />
    );
  }

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setInfoMsg('');

    // Format check
    if (!phoneNumber.startsWith('+')) {
      setError("Phone number must include country code (e.g. +919876543210)");
      setLoading(false);
      return;
    }

    try {
      const appVerifier = window.recaptchaVerifier;
      const confirmation = await signInWithPhoneNumber(auth, phoneNumber, appVerifier);
      setConfirmationResult(confirmation);
      setInfoMsg("OTP sent successfully to " + phoneNumber);
    } catch (err) {
      console.error("Firebase SMS failed. Offering local bypass.", err);
      setError("Firebase SMS limit/quota exceeded or unconfigured. Please use the 'Local Developer Bypass' below.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await confirmationResult.confirm(otp);
      const user = result.user;
      const idToken = await user.getIdToken();
      
      // Send token to FastAPI backend
      await submitToBackend(phoneNumber, idToken);
    } catch (err) {
      console.error(err);
      setError("Invalid OTP code. Please check and try again.");
      setLoading(false);
    }
  };

  // Graceful local developer bypass
  const handleBypassLogin = async () => {
    setError(null);
    setLoading(true);
    
    const testPhone = phoneNumber.trim() || (role === 'owner' ? '+919999988888' : '+919876543210');
    const mockToken = "mock_token_" + testPhone;
    
    try {
      await submitToBackend(testPhone, mockToken);
    } catch (err) {
      console.error(err);
      setError("Failed to connect to the backend server. Is FastAPI running on port 8000?");
      setLoading(false);
    }
  };

  const submitToBackend = async (phone, token) => {
    const res = await fetch(`${backendUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phone,
        firebase_id_token: token,
        role: role
      })
    });

    if (!res.ok) {
      const detail = await res.json();
      throw new Error(detail.detail || "Backend login failed");
    }

    const session = await res.json();
    localStorage.setItem('retail_session', JSON.stringify(session));
    onLoginSuccess(session);
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px', color: 'var(--primary)' }}>
          <ShieldCheck size={48} />
        </div>
        
        <h2 className="auth-title">Welcome to Retail Automate</h2>
        <p className="auth-subtitle">Select role and log in with your phone number</p>

        <div className="role-selector">
          <div 
            className={`role-option ${role === 'customer' ? 'active' : ''}`}
            onClick={() => setRole('customer')}
          >
            👨‍💼 Customer
          </div>
          <div 
            className={`role-option ${role === 'owner' ? 'active' : ''}`}
            onClick={() => setRole('owner')}
          >
            🏪 Shop Owner
          </div>
        </div>

        {role === 'owner' && (
          <div style={{ 
            marginBottom: '20px', 
            padding: '12px', 
            backgroundColor: 'var(--primary-light)', 
            borderRadius: 'var(--radius-sm)', 
            display: 'flex', 
            alignItems: 'center', 
            justify: 'space-between',
            border: '1px solid var(--surface-border)'
          }}>
            <span style={{ fontSize: '13px', color: 'var(--primary)', fontWeight: '500' }}>New Shop Owner?</span>
            <button 
              type="button" 
              className="btn-logout" 
              style={{ borderColor: 'var(--primary)', color: 'var(--primary)', fontWeight: '600', padding: '4px 12px', fontSize: '12px' }}
              onClick={() => setIsRegisteringOwner(true)}
            >
              Create Owner Account
            </button>
          </div>
        )}

        {error && (
          <div style={{
            backgroundColor: 'var(--error-light)', 
            color: 'var(--error)', 
            padding: '12px', 
            borderRadius: 'var(--radius-sm)', 
            fontSize: '13px', 
            marginBottom: '20px',
            borderLeft: '4px solid var(--error)',
            fontWeight: '500'
          }}>
            {error}
          </div>
        )}

        {infoMsg && (
          <div style={{
            backgroundColor: 'var(--secondary-light)', 
            color: 'var(--secondary)', 
            padding: '12px', 
            borderRadius: 'var(--radius-sm)', 
            fontSize: '13px', 
            marginBottom: '20px',
            borderLeft: '4px solid var(--secondary)'
          }}>
            {infoMsg}
          </div>
        )}

        {!confirmationResult ? (
          <form onSubmit={handleSendOtp}>
            <div className="form-group">
              <label className="form-label">Phone Number</label>
              <div style={{ position: 'relative' }}>
                <Phone size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: 'var(--text-secondary)' }} />
                <input 
                  type="tel" 
                  className="form-input" 
                  style={{ paddingLeft: '42px' }}
                  placeholder="+919876543210" 
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  required
                />
              </div>
            </div>
            
            <div id="recaptcha-container"></div>
            
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Sending..." : "Send OTP via SMS"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp}>
            <div className="form-group">
              <label className="form-label">Enter 6-Digit OTP</label>
              <div style={{ position: 'relative' }}>
                <Key size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: 'var(--text-secondary)' }} />
                <input 
                  type="text" 
                  className="form-input" 
                  style={{ paddingLeft: '42px' }}
                  placeholder="123456" 
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  maxLength={6}
                  required
                />
              </div>
            </div>
            
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Verifying..." : "Verify OTP"}
            </button>
            
            <button 
              type="button" 
              className="btn-logout" 
              style={{ width: '100%', marginTop: '10px' }}
              onClick={() => setConfirmationResult(null)}
            >
              Change Phone Number
            </button>
          </form>
        )}

        {showBypass && (
          <div style={{ 
            marginTop: '24px', 
            paddingTop: '20px', 
            borderTop: '1px solid var(--surface-border)', 
            textAlign: 'center' 
          }}>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
              <HelpCircle size={14} /> Testing mode without Firebase configured?
            </p>
            <button 
              type="button" 
              className="btn-logout" 
              style={{ width: '100%', borderColor: 'var(--primary)', color: 'var(--primary)', backgroundColor: 'var(--primary-light)' }}
              onClick={handleBypassLogin}
              disabled={loading}
            >
              Developer Login Bypass (Free)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
