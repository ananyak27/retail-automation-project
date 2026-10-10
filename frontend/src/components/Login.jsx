import React, { useState, useEffect } from 'react';
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { ShieldCheck, Phone, Key, HelpCircle, User, ArrowRight, UserPlus, LogIn } from 'lucide-react';
import OwnerRegister from './OwnerRegister';

const getEffectiveBackendUrl = (propBackendUrl) => {
  if (import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  const hostname = window.location.hostname;
  if (hostname) {
    return `http://${hostname}:8000`;
  }
  if (propBackendUrl) {
    return propBackendUrl;
  }
  return 'http://localhost:8000';
};

export default function Login({ onLoginSuccess, backendUrl: propBackendUrl }) {
  const backendUrl = getEffectiveBackendUrl(propBackendUrl);
  const [isRegisteringOwner, setIsRegisteringOwner] = useState(false);
  const [role, setRole] = useState('customer'); // 'customer' or 'owner'
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register' (for customer)

  // Form fields
  const [phoneNumber, setPhoneNumber] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [otp, setOtp] = useState('');

  // Firebase OTP & Flow state
  const [confirmationResult, setConfirmationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMsg, setInfoMsg] = useState('');
  const [suggestRegistration, setSuggestRegistration] = useState(false);
  const [suggestLogin, setSuggestLogin] = useState(false);
  const [showBypass, setShowBypass] = useState(true);

  useEffect(() => {
    let verifier = null;
    if (!confirmationResult && !isRegisteringOwner) {
      try {
        const container = document.getElementById('recaptcha-container');
        if (container) {
          if (window.recaptchaVerifier) {
            try { window.recaptchaVerifier.clear(); } catch (e) {}
          }
          verifier = new RecaptchaVerifier(auth, container, {
            size: 'invisible',
            callback: () => {}
          });
          window.recaptchaVerifier = verifier;
        }
      } catch (err) {
        console.warn("Firebase reCAPTCHA initialization error:", err);
      }
    }

    return () => {
      if (window.recaptchaVerifier) {
        try { window.recaptchaVerifier.clear(); } catch (e) {}
        window.recaptchaVerifier = null;
      }
    };
  }, [isRegisteringOwner, confirmationResult, role, authMode]);

  const cleanPhone = (phone) => {
    return phone.trim().replace(/\s+/g, '');
  };

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    setError(null);
    setInfoMsg('');
    setConfirmationResult(null);
    setOtp('');
    setSuggestRegistration(false);
    setSuggestLogin(false);
  };

  const handleModeChange = (newMode) => {
    setAuthMode(newMode);
    setError(null);
    setInfoMsg('');
    setConfirmationResult(null);
    setOtp('');
    setSuggestRegistration(false);
    setSuggestLogin(false);
  };

  const handleGoToLogin = () => {
    setAuthMode('login');
    setError(null);
    setInfoMsg('');
    setConfirmationResult(null);
    setOtp('');
    setSuggestLogin(false);
    setSuggestRegistration(false);
  };

  if (isRegisteringOwner) {
    return (
      <OwnerRegister
        onLoginSuccess={onLoginSuccess}
        onBackToLogin={(data) => {
          setIsRegisteringOwner(false);
          if (data && data.phoneNumber) {
            setPhoneNumber(data.phoneNumber);
          }
        }}
        initialPhoneNumber={phoneNumber}
        backendUrl={backendUrl}
      />
    );
  }

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMsg('');
    setSuggestRegistration(false);
    setSuggestLogin(false);

    const formattedPhone = cleanPhone(phoneNumber);
    if (!formattedPhone.startsWith('+')) {
      setError("Phone number must include country code (e.g. +919876543210)");
      return;
    }

    if (role === 'customer' && authMode === 'register' && !customerName.trim()) {
      setError("Please enter your name.");
      return;
    }

    setLoading(true);

    try {
      // PRE-OTP ACCOUNT EXISTENCE CHECK BEFORE SENDING OTP
      const checkRes = await fetch(`${backendUrl}/api/auth/check-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: formattedPhone, name: customerName || null })
      });

      if (!checkRes.ok) {
        const errorData = await checkRes.json().catch(() => ({}));
        throw new Error(errorData.detail || "Account check failed. Please check backend connection.");
      }

      const accountData = await checkRes.json();

      // 1. REGISTRATION MODE CHECKS
      if (role === 'customer' && authMode === 'register') {
        if (accountData.exists) {
          setLoading(false);
          if (accountData.role === 'owner') {
            setError("An account with this name and phone number already exists as an owner. Please use the owner login.");
            return;
          } else {
            setError("An account with this name and phone number already exists. Please log in.");
            setSuggestLogin(true);
            return;
          }
        }
      }
      // 2. LOGIN MODE CHECKS
      else {
        if (role === 'customer') {
          if (!accountData.exists) {
            setLoading(false);
            setError("No customer account found with this phone number. Please register first.");
            setSuggestRegistration(true);
            return;
          } else if (accountData.role === 'owner') {
            setLoading(false);
            setError("This phone number belongs to an owner account. Please use the owner login.");
            return;
          }
        } else if (role === 'owner') {
          if (!accountData.exists) {
            setLoading(false);
            setError("No owner account found with this phone number. Please register first.");
            setSuggestRegistration(true);
            return;
          } else if (accountData.role === 'customer') {
            setLoading(false);
            setError("This phone number belongs to a customer account. Please use the customer login.");
            return;
          }
        }
      }

      let appVerifier = window.recaptchaVerifier;
      if (!appVerifier) {
        const container = document.getElementById('recaptcha-container');
        if (container) {
          appVerifier = new RecaptchaVerifier(auth, container, {
            size: 'invisible',
            callback: () => {}
          });
          window.recaptchaVerifier = appVerifier;
        }
      }

      if (!appVerifier) {
        throw new Error("reCAPTCHA verifier not initialized. Please refresh the page.");
      }

      const confirmation = await signInWithPhoneNumber(auth, formattedPhone, appVerifier);
      setConfirmationResult(confirmation);
      setInfoMsg(`OTP sent successfully to ${formattedPhone}. Enter the OTP sent to your phone.`);
    } catch (err) {
      console.error("Firebase SMS failed:", err);
      if (err.code === 'auth/invalid-phone-number') {
        setError("Invalid phone number format. Please check the country code and number.");
      } else if (err.code === 'auth/too-many-requests' || err.code === 'auth/quota-exceeded') {
        setError("Firebase SMS limit/quota exceeded. Please use 'Developer Login Bypass (Free)' below.");
      } else {
        setError(err.message || "Failed to send OTP via SMS. Check Firebase setup or use Developer Bypass.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMsg('');
    setLoading(true);

    try {
      const result = await confirmationResult.confirm(otp);
      const user = result.user;
      const idToken = await user.getIdToken();

      const formattedPhone = cleanPhone(phoneNumber);
      if (role === 'customer' && authMode === 'register') {
        await submitCustomerRegistration(formattedPhone, idToken);
      } else {
        await submitLogin(formattedPhone, idToken);
      }
    } catch (err) {
      console.error("Verification failed:", err);
      if (err.code === 'auth/invalid-verification-code') {
        setError("Invalid OTP code. Please check and try again.");
      } else if (err.code === 'auth/code-expired') {
        setError("OTP code has expired. Please click 'Change Phone Number' to request a new OTP.");
      } else {
        setError(err.message || "Invalid OTP verification code.");
      }
      setLoading(false);
    }
  };

  // Local developer bypass
  const handleBypassLogin = async () => {
    setError(null);
    setInfoMsg('');
    setSuggestLogin(false);
    setSuggestRegistration(false);

    if (!phoneNumber.trim()) {
      setError("Please enter your Phone Number first.");
      return;
    }

    const formattedPhone = cleanPhone(phoneNumber);
    if (!formattedPhone.startsWith('+')) {
      setError("Phone number must include country code (e.g. +919876543210)");
      return;
    }

    if (role === 'customer' && authMode === 'register' && !customerName.trim()) {
      setError("Please enter your name.");
      return;
    }

    setLoading(true);

    try {
      const checkRes = await fetch(`${backendUrl}/api/auth/check-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: formattedPhone, name: customerName || null })
      });

      if (checkRes.ok) {
        const accountData = await checkRes.json();

        if (role === 'customer' && authMode === 'register') {
          if (accountData.exists) {
            setLoading(false);
            if (accountData.role === 'owner') {
              setError("An account with this name and phone number already exists as an owner. Please use the owner login.");
              return;
            } else {
              setError("An account with this name and phone number already exists. Please log in.");
              setSuggestLogin(true);
              return;
            }
          }
        } else {
          if (role === 'customer') {
            if (!accountData.exists) {
              setLoading(false);
              setError("No customer account found with this phone number. Please register first.");
              setSuggestRegistration(true);
              return;
            } else if (accountData.role === 'owner') {
              setLoading(false);
              setError("This phone number belongs to an owner account. Please use the owner login.");
              return;
            }
          } else if (role === 'owner') {
            if (!accountData.exists) {
              setLoading(false);
              setError("No owner account found with this phone number. Please register first.");
              setSuggestRegistration(true);
              return;
            } else if (accountData.role === 'customer') {
              setLoading(false);
              setError("This phone number belongs to a customer account. Please use the customer login.");
              return;
            }
          }
        }
      }

      const mockToken = "mock_token_" + formattedPhone;
      if (role === 'customer' && authMode === 'register') {
        await submitCustomerRegistration(formattedPhone, mockToken);
      } else {
        await submitLogin(formattedPhone, mockToken);
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const submitLogin = async (phone, token) => {
    try {
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
        const msg = detail.detail || "Backend login failed";
        if (res.status === 404 || msg.includes("Account not available")) {
          setSuggestRegistration(true);
          throw new Error(msg);
        }
        throw new Error(msg);
      }

      const session = await res.json();
      sessionStorage.setItem('retail_session', JSON.stringify(session));
      onLoginSuccess(session);
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  const submitCustomerRegistration = async (phone, token) => {
    try {
      const res = await fetch(`${backendUrl}/api/auth/register-customer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number: phone,
          firebase_id_token: token,
          customer_name: customerName || null
        })
      });

      if (!res.ok) {
        const detail = await res.json();
        const msg = detail.detail || "Customer registration failed";
        if (res.status === 400 || msg.includes("Account already exists")) {
          setSuggestLogin(true);
          throw new Error("An account with this name and phone number already exists. Please log in.");
        }
        throw new Error(msg);
      }

      const session = await res.json();
      sessionStorage.setItem('retail_session', JSON.stringify(session));
      onLoginSuccess(session);
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  const resetOtpState = () => {
    setConfirmationResult(null);
    setOtp('');
    setError(null);
    setInfoMsg('');
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px', color: 'var(--primary)' }}>
          <ShieldCheck size={48} />
        </div>

        <h2 className="auth-title">Welcome to Retail Automate</h2>
        <p className="auth-subtitle">Select role and proceed with phone verification</p>

        {/* Role Selector */}
        <div className="role-selector">
          <div
            className={`role-option ${role === 'customer' ? 'active' : ''}`}
            onClick={() => handleRoleChange('customer')}
          >
            👨‍💼 Customer
          </div>
          <div
            className={`role-option ${role === 'owner' ? 'active' : ''}`}
            onClick={() => handleRoleChange('owner')}
          >
            🏪 Shop Owner
          </div>
        </div>

        {/* Customer Mode Selector (Login vs Create Account) */}
        {role === 'customer' && (
          <div style={{
            display: 'flex',
            gap: '8px',
            marginBottom: '20px',
            padding: '4px',
            backgroundColor: 'var(--surface-light)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--surface-border)'
          }}>
            <button
              type="button"
              style={{
                flex: 1,
                padding: '8px',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: '600',
                cursor: 'pointer',
                backgroundColor: authMode === 'login' ? 'var(--primary)' : 'transparent',
                color: authMode === 'login' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s'
              }}
              onClick={() => handleModeChange('login')}
            >
              Customer Login
            </button>
            <button
              type="button"
              style={{
                flex: 1,
                padding: '8px',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: '600',
                cursor: 'pointer',
                backgroundColor: authMode === 'register' ? 'var(--primary)' : 'transparent',
                color: authMode === 'register' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s'
              }}
              onClick={() => handleModeChange('register')}
            >
              Create Account
            </button>
          </div>
        )}

        {/* Owner Registration Header Banner */}
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

        {/* Error Display */}
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
            <div>{error}</div>

            {/* Action button if account not available */}
            {suggestRegistration && (
              <button
                type="button"
                className="btn-primary"
                style={{ marginTop: '10px', width: '100%', fontSize: '12px', padding: '8px 12px', backgroundColor: 'var(--error)' }}
                onClick={() => {
                  setError(null);
                  setSuggestRegistration(false);
                  if (role === 'customer') {
                    setAuthMode('register');
                  } else {
                    setIsRegisteringOwner(true);
                  }
                }}
              >
                <UserPlus size={14} style={{ marginRight: '6px' }} /> Create New Account
              </button>
            )}

            {/* Action button if account already exists */}
            {suggestLogin && (
              <button
                type="button"
                className="btn-primary"
                style={{ marginTop: '10px', width: '100%', fontSize: '12px', padding: '8px 12px', backgroundColor: 'var(--primary)' }}
                onClick={handleGoToLogin}
              >
                <LogIn size={14} style={{ marginRight: '6px' }} /> Go to Login
              </button>
            )}
          </div>
        )}

        {/* Info Message Display */}
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

        {/* Step 1: Phone Entry & Send OTP */}
        {!confirmationResult ? (
          <form onSubmit={handleSendOtp}>
            {role === 'customer' && authMode === 'register' && (
              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <div style={{ position: 'relative' }}>
                  <User size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: 'var(--text-secondary)' }} />
                  <input
                    type="text"
                    className="form-input"
                    style={{ paddingLeft: '42px' }}
                    placeholder="John Doe"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Phone Number *</label>
              <div style={{ position: 'relative' }}>
                <Phone size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: 'var(--text-secondary)' }} />
                <input
                  type="tel"
                  className="form-input"
                  style={{ paddingLeft: '42px' }}
                  placeholder="Enter phone number"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  required
                />
              </div>
            </div>

            <div id="recaptcha-container"></div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Sending OTP..." : "Send Firebase OTP via SMS"}
            </button>
          </form>
        ) : (
          /* Step 2: OTP Verification Field */
          <form onSubmit={handleVerifyOtp}>
            <div className="form-group">
              <label className="form-label">Enter 6-Digit Verification Code *</label>
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
              {loading
                ? "Verifying..."
                : (role === 'customer' && authMode === 'register')
                  ? "Verify OTP & Create Account"
                  : "Verify OTP & Login"}
            </button>

            <button
              type="button"
              className="btn-logout"
              style={{ width: '100%', marginTop: '10px' }}
              onClick={resetOtpState}
            >
              Change Phone Number
            </button>
          </form>
        )}

        {/* Developer Registration / Login Bypass */}
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
              Developer Registration Bypass (Free)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
