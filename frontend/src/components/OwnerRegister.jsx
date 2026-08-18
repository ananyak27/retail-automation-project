import React, { useState, useEffect } from 'react';
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { ShieldCheck, Phone, Key, HelpCircle, User, Store, CreditCard, ArrowLeft } from 'lucide-react';

export default function OwnerRegister({ onLoginSuccess, onBackToLogin, backendUrl }) {
  // 1. Personal Information
  const [ownerName, setOwnerName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');

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

  useEffect(() => {
    if (!confirmationResult) {
      try {
        const container = document.getElementById('recaptcha-container-owner');
        if (container) {
          window.recaptchaVerifierOwner = new RecaptchaVerifier(auth, container, {
            size: 'invisible',
            callback: () => {}
          });
        }
      } catch (err) {
        console.warn("Firebase reCAPTCHA initialization failed. Local Bypass will be available.", err);
      }
    }
  }, [confirmationResult]);

  const validateForm = () => {
    if (!ownerName.trim()) {
      setError("Please enter Owner Name.");
      return false;
    }
    if (!phoneNumber.startsWith('+')) {
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

    if (!validateForm()) return;

    setLoading(true);
    try {
      const appVerifier = window.recaptchaVerifierOwner;
      const confirmation = await signInWithPhoneNumber(auth, phoneNumber, appVerifier);
      setConfirmationResult(confirmation);
      setInfoMsg("OTP sent successfully to " + phoneNumber);
    } catch (err) {
      console.error("Firebase SMS failed.", err);
      setError("Firebase SMS limit/quota exceeded or unconfigured. Please use the 'Developer Registration Bypass' below.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtpAndRegister = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await confirmationResult.confirm(otp);
      const user = result.user;
      const idToken = await user.getIdToken();

      await submitOwnerRegistration(idToken);
    } catch (err) {
      console.error(err);
      setError(err.message || "Invalid OTP code or registration failed. Please try again.");
      setLoading(false);
    }
  };

  const handleBypassRegistration = async () => {
    setError(null);
    if (!validateForm()) return;

    setLoading(true);
    const testPhone = phoneNumber.trim() || '+919999988888';
    const mockToken = "mock_token_" + testPhone;

    try {
      await submitOwnerRegistration(mockToken, testPhone);
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to connect to backend server. Is FastAPI running on port 8000?");
      setLoading(false);
    }
  };

  const submitOwnerRegistration = async (idToken, overridePhone = null) => {
    const payload = {
      owner_name: ownerName,
      phone_number: overridePhone || phoneNumber,
      firebase_id_token: idToken,
      shop_name: shopName,
      shop_address: shopAddress,
      bank_account_holder_name: bankAccountHolderName,
      bank_name: bankName,
      account_number: accountNumber,
      ifsc_code: ifscCode,
      upi_id: upiId || null
    };

    const res = await fetch(`${backendUrl}/api/auth/register-owner`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const detail = await res.json();
      throw new Error(detail.detail || "Owner registration failed.");
    }

    const session = await res.json();
    localStorage.setItem('retail_session', JSON.stringify(session));
    onLoginSuccess(session);
  };

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ maxWidth: '640px' }}>
        <button 
          type="button"
          onClick={onBackToLogin}
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
                    placeholder="+919876543210"
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
              <label className="form-label">Enter 6-Digit Verification Code</label>
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
              onClick={() => setConfirmationResult(null)}
            >
              Change Registration Form / Phone Number
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
