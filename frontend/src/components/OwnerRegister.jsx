import React, { useState, useEffect } from 'react';
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { ShieldCheck, Phone, Key, HelpCircle, User, Store, CreditCard, ArrowLeft, LogIn } from 'lucide-react';

export default function OwnerRegister({ onLoginSuccess, onBackToLogin, backendUrl, initialPhoneNumber = '' }) {
  // 1. Personal Information
  const [ownerName, setOwnerName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState(initialPhoneNumber);

  // 2. Business Information
  const [shopName, setShopName] = useState('');
  const [shopAddress, setShopAddress] = useState('');

  // 3. Payment Information
  const [bankAccountHolderName, setBankAccountHolderName] = useState('');
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifscCode, setIfscCode] = useState('');
  const [upiId, setUpiId] = useState('');

  // OTP State
  const [otp, setOtp] = useState('');
  const [confirmationResult, setConfirmationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMsg, setInfoMsg] = useState('');
  const [suggestLogin, setSuggestLogin] = useState(false);

  useEffect(() => {
    let verifier = null;
    if (!confirmationResult) {
      try {
        const container = document.getElementById('recaptcha-container-owner');
        if (container) {
          if (window.recaptchaVerifierOwner) {
            try { window.recaptchaVerifierOwner.clear(); } catch (e) {}
          }
          verifier = new RecaptchaVerifier(auth, container, {
            size: 'invisible',
            callback: () => {}
          });
          window.recaptchaVerifierOwner = verifier;
        }
      } catch (err) {
        console.warn("Firebase reCAPTCHA initialization error:", err);
      }
    }

    return () => {
      if (window.recaptchaVerifierOwner) {
        try { window.recaptchaVerifierOwner.clear(); } catch (e) {}
        window.recaptchaVerifierOwner = null;
      }
    };
  }, [confirmationResult]);

  const cleanPhone = (phone) => {
    return phone.trim().replace(/\s+/g, '');
  };

  const validateForm = () => {
    if (!ownerName.trim()) {
      setError("Please enter Owner Name.");
      return false;
    }
    const formattedPhone = cleanPhone(phoneNumber);
    if (!formattedPhone.startsWith('+')) {
      setError("Phone number must include country code (e.g. +919876543210)");
      return false;
    }
    if (!shopName.trim()) {
      setError("Please enter Shop Name.");
      return false;
    }
    if (!shopAddress.trim()) {
      setError("Please enter Shop Address.");
      return false;
    }
    if (!bankAccountHolderName.trim()) {
      setError("Please enter Bank Account Holder Name.");
      return false;
    }
    if (!bankName.trim()) {
      setError("Please enter Bank Name.");
      return false;
    }
    if (!accountNumber.trim()) {
      setError("Please enter Account Number.");
      return false;
    }
    if (!ifscCode.trim()) {
      setError("Please enter IFSC Code.");
      return false;
    }
    return true;
  };

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMsg('');
    setSuggestLogin(false);

    if (!validateForm()) return;

    setLoading(true);
    const formattedPhone = cleanPhone(phoneNumber);

    try {
      // PRE-OTP ACCOUNT EXISTENCE CHECK BEFORE SENDING OTP
      const checkRes = await fetch(`${backendUrl}/api/auth/check-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: formattedPhone, name: ownerName })
      });

      if (checkRes.ok) {
        const accountData = await checkRes.json();
        if (accountData.exists) {
          setLoading(false);
          if (accountData.role === 'customer') {
            setError("An account with this name and phone number already exists as a customer. Please use the customer login.");
            return;
          } else {
            setError("An account with this name and phone number already exists. Please log in.");
            setSuggestLogin(true);
            return;
          }
        }
      }

      const appVerifier = window.recaptchaVerifierOwner;
      if (!appVerifier) {
        throw new Error("reCAPTCHA verifier not initialized. Please refresh the page.");
      }
      const confirmation = await signInWithPhoneNumber(auth, formattedPhone, appVerifier);
      setConfirmationResult(confirmation);
      setInfoMsg(`OTP sent successfully to ${formattedPhone}. Enter the OTP sent to your phone.`);
    } catch (err) {
      console.error("Firebase SMS failed.", err);
      if (err.code === 'auth/invalid-phone-number') {
        setError("Invalid phone number format. Please check the country code and number.");
      } else if (err.code === 'auth/too-many-requests' || err.code === 'auth/quota-exceeded') {
        setError("Firebase SMS limit/quota exceeded. Please use 'Developer Registration Bypass (Free)' below.");
      } else {
        setError(err.message || "Firebase SMS limit/quota exceeded or unconfigured. Please use 'Developer Registration Bypass' below.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtpAndRegister = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMsg('');
    setLoading(true);

    try {
      const result = await confirmationResult.confirm(otp);
      const user = result.user;
      const idToken = await user.getIdToken();

      const formattedPhone = cleanPhone(phoneNumber);
      await submitOwnerRegistration(idToken, formattedPhone);
    } catch (err) {
      console.error(err);
      if (err.code === 'auth/invalid-verification-code') {
        setError("Invalid OTP code. Please check and try again.");
      } else if (err.code === 'auth/code-expired') {
        setError("OTP code has expired. Please click 'Change Phone Number' to request a new OTP.");
      } else {
        setError(err.message || "Invalid OTP code or registration failed. Please try again.");
      }
      setLoading(false);
    }
  };

  const handleBypassRegistration = async () => {
    setError(null);
    setInfoMsg('');
    setSuggestLogin(false);

    if (!validateForm()) return;

    setLoading(true);
    const formattedPhone = cleanPhone(phoneNumber);

    try {
      // Pre-check for bypass as well
      const checkRes = await fetch(`${backendUrl}/api/auth/check-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: formattedPhone, name: ownerName })
      });

      if (checkRes.ok) {
        const accountData = await checkRes.json();
        if (accountData.exists) {
          setLoading(false);
          if (accountData.role === 'customer') {
            setError("An account with this name and phone number already exists as a customer. Please use the customer login.");
            return;
          } else {
            setError("An account with this name and phone number already exists. Please log in.");
            setSuggestLogin(true);
            return;
          }
        }
      }

      const mockToken = "mock_token_" + formattedPhone;
      await submitOwnerRegistration(mockToken, formattedPhone);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const submitOwnerRegistration = async (idToken, overridePhone = null) => {
    const payload = {
      owner_name: ownerName,
      phone_number: overridePhone || cleanPhone(phoneNumber),
      firebase_id_token: idToken,
      shop_name: shopName,
      shop_address: shopAddress,
      bank_account_holder_name: bankAccountHolderName,
      bank_name: bankName,
      account_number: accountNumber,
      ifsc_code: ifscCode,
      upi_id: upiId || null
    };

    try {
      const res = await fetch(`${backendUrl}/api/auth/register-owner`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const detail = await res.json();
        const msg = detail.detail || "Owner registration failed.";
        if (res.status === 400 || msg.includes("Account already exists")) {
          setSuggestLogin(true);
          throw new Error("An account with this name and phone number already exists. Please log in.");
        }
        throw new Error(msg);
      }

      const session = await res.json();
      localStorage.setItem('retail_session', JSON.stringify(session));
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
      <div className="auth-card" style={{ maxWidth: '640px' }}>
        <button 
          type="button"
          onClick={() => onBackToLogin({ phoneNumber })}
          className="btn-logout"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginBottom: '16px', padding: '6px 12px' }}
        >
          <ArrowLeft size={16} /> Back to Login
        </button>

        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px', color: 'var(--primary)' }}>
          <ShieldCheck size={44} />
        </div>

        <h2 className="auth-title">Shop Owner Registration</h2>
        <p className="auth-subtitle">Fill in your business and bank details to set up your retail account</p>

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

            {suggestLogin && (
              <button
                type="button"
                className="btn-primary"
                style={{ marginTop: '10px', width: '100%', fontSize: '12px', padding: '8px 12px', backgroundColor: 'var(--primary)' }}
                onClick={() => onBackToLogin({ phoneNumber })}
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

        {!confirmationResult ? (
          <form onSubmit={handleSendOtp}>
            {/* SECTION 1: PERSONAL INFORMATION */}
            <div style={{ marginBottom: '24px', backgroundColor: 'var(--surface-light)', padding: '16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)' }}>
                <User size={18} /> 1. PERSONAL INFORMATION
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Owner Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="John Doe"
                    value={ownerName}
                    onChange={(e) => setOwnerName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Mobile Number *</label>
                  <input
                    type="tel"
                    className="form-input"
                    placeholder="Enter phone number"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            {/* SECTION 2: BUSINESS INFORMATION */}
            <div style={{ marginBottom: '24px', backgroundColor: 'var(--surface-light)', padding: '16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)' }}>
                <Store size={18} /> 2. BUSINESS INFORMATION
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Shop Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Fresh Supermart"
                    value={shopName}
                    onChange={(e) => setShopName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Shop Address *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="123 Main St, Market Square, City"
                    value={shopAddress}
                    onChange={(e) => setShopAddress(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            {/* SECTION 3: PAYMENT INFORMATION */}
            <div style={{ marginBottom: '24px', backgroundColor: 'var(--surface-light)', padding: '16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--surface-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)' }}>
                <CreditCard size={18} /> 3. PAYMENT INFORMATION
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Bank Account Holder Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="John Doe"
                    value={bankAccountHolderName}
                    onChange={(e) => setBankAccountHolderName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Bank Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="State Bank of India / HDFC"
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Account Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="123456789012"
                    value={accountNumber}
                    onChange={(e) => setAccountNumber(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">IFSC Code *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="SBIN0001234"
                    value={ifscCode}
                    onChange={(e) => setIfscCode(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">UPI ID (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="john@upi"
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div id="recaptcha-container-owner"></div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Sending OTP..." : "Send Firebase OTP via SMS"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtpAndRegister}>
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
              {loading ? "Registering Shop Owner..." : "Verify OTP & Complete Registration"}
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

        <div style={{
          marginTop: '24px',
          paddingTop: '20px',
          borderTop: '1px solid var(--surface-border)',
          textAlign: 'center'
        }}>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
            <HelpCircle size={14} /> Testing mode without Firebase active?
          </p>
          <button
            type="button"
            className="btn-logout"
            style={{ width: '100%', borderColor: 'var(--primary)', color: 'var(--primary)', backgroundColor: 'var(--primary-light)' }}
            onClick={handleBypassRegistration}
            disabled={loading}
          >
            Developer Registration Bypass (Free)
          </button>
        </div>
      </div>
    </div>
  );
}
