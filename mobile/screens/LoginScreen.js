import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';

import { saveSession } from '../utils/storage';
import { colors, sharedStyles, radius } from '../styles/theme';
import { BACKEND_URL, auth } from '../firebaseConfig';


export default function LoginScreen({ navigation, onLoginSuccess }) {
  const [role, setRole] = useState('customer');         // 'customer' | 'owner'
  const [authMode, setAuthMode] = useState('login');    // 'login' | 'register'
  const [phoneNumber, setPhoneNumber] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [otp, setOtp] = useState('');
  const [confirmationResult, setConfirmationResult] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMsg, setInfoMsg] = useState('');
  const [suggestRegistration, setSuggestRegistration] = useState(false);
  const [suggestLogin, setSuggestLogin] = useState(false);

  const cleanPhone = (p) => p.trim().replace(/\s+/g, '');

  const resetState = () => {
    setError(null);
    setInfoMsg('');
    setSuggestRegistration(false);
    setSuggestLogin(false);
  };

  const handleRoleChange = (r) => {
    setRole(r);
    setConfirmationResult(null);
    setOtp('');
    resetState();
  };

  const handleModeChange = (m) => {
    setAuthMode(m);
    setConfirmationResult(null);
    setOtp('');
    resetState();
  };

  // ─── Pre-check account existence ───────────────────────────────────────────
  const checkAccount = async (phone) => {
    const res = await fetch(`${BACKEND_URL}/api/auth/check-account`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone_number: phone, name: customerName || null }),
    });
    if (res.ok) return await res.json();
    return null;
  };

  const validateAccountForMode = async (phone) => {
    const accountData = await checkAccount(phone);
    if (!accountData) return true; // Skip check if endpoint fails

    if (role === 'customer' && authMode === 'register') {
      if (accountData.exists) {
        if (accountData.role === 'owner') {
          setError('An account already exists as an owner. Use owner login.');
        } else {
          setError('Account already exists. Please log in.');
          setSuggestLogin(true);
        }
        return false;
      }
    } else {
      if (role === 'customer') {
        if (!accountData.exists) {
          setError('No customer account found. Please register first.');
          setSuggestRegistration(true);
          return false;
        }
        if (accountData.role === 'owner') {
          setError('This number belongs to an owner account. Use owner login.');
          return false;
        }
      } else if (role === 'owner') {
        if (!accountData.exists) {
          setError('No owner account found. Please register first.');
          setSuggestRegistration(true);
          return false;
        }
        if (accountData.role === 'customer') {
          setError('This number belongs to a customer account. Use customer login.');
          return false;
        }
      }
    }
    return true;
  };

  // ─── Send OTP via Firebase ──────────────────────────────────────────────────
  const handleSendOtp = async () => {
    resetState();
    const phone = cleanPhone(phoneNumber);
    if (!phone.startsWith('+')) {
      setError('Phone number must include country code (e.g. +919876543210)');
      return;
    }
    if (role === 'customer' && authMode === 'register' && !customerName.trim()) {
      setError('Please enter your full name.');
      return;
    }

    setLoading(true);
    try {
      const valid = await validateAccountForMode(phone);
      if (!valid) { setLoading(false); return; }

      // Firebase JS SDK — works in Expo Go (web-compatible phone auth)
      const confirmation = await signInWithPhoneNumber(auth, phone);
      setConfirmationResult(confirmation);
      setInfoMsg(`OTP sent to ${phone}. Enter the 6-digit code.`);
    } catch (err) {
      if (err.code === 'auth/invalid-phone-number') {
        setError('Invalid phone number format.');
      } else if (err.code === 'auth/too-many-requests') {
        setError('Too many OTP requests. Please try the Developer Bypass below.');
      } else if (err.code === 'auth/captcha-check-failed') {
        setError('reCAPTCHA check failed. Use the Developer Bypass for local testing.');
      } else {
        setError(err.message || 'Failed to send OTP. Use Developer Bypass for local testing.');
      }
    } finally {
      setLoading(false);
    }
  };


  // ─── Verify OTP and login/register ─────────────────────────────────────────
  const handleVerifyOtp = async () => {
    resetState();
    setLoading(true);
    const phone = cleanPhone(phoneNumber);
    try {
      const result = await confirmationResult.confirm(otp);
      const idToken = await result.user.getIdToken();

      if (role === 'customer' && authMode === 'register') {
        await submitCustomerRegistration(phone, idToken);
      } else {
        await submitLogin(phone, idToken);
      }
    } catch (err) {
      if (err.code === 'auth/invalid-verification-code') {
        setError('Invalid OTP code.');
      } else if (err.code === 'auth/code-expired') {
        setError('OTP expired. Tap "Change Phone" to resend.');
      } else {
        setError(err.message || 'OTP verification failed.');
      }
      setLoading(false);
    }
  };

  // ─── Developer bypass (no Firebase OTP) ────────────────────────────────────
  const handleBypassLogin = async () => {
    resetState();
    const phone = cleanPhone(phoneNumber);
    if (!phone) { setError('Enter your phone number first.'); return; }
    if (!phone.startsWith('+')) {
      setError('Phone must include country code (e.g. +919876543210)');
      return;
    }
    if (role === 'customer' && authMode === 'register' && !customerName.trim()) {
      setError('Enter your full name first.');
      return;
    }
    setLoading(true);
    try {
      const valid = await validateAccountForMode(phone);
      if (!valid) { setLoading(false); return; }

      const mockToken = 'mock_token_' + phone;
      if (role === 'customer' && authMode === 'register') {
        await submitCustomerRegistration(phone, mockToken);
      } else {
        await submitLogin(phone, mockToken);
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const submitLogin = async (phone, token) => {
    const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone_number: phone, firebase_id_token: token, role }),
    });
    if (!res.ok) {
      const detail = await res.json();
      const msg = detail.detail || 'Login failed';
      if (res.status === 404 || msg.includes('Account not available')) setSuggestRegistration(true);
      throw new Error(msg);
    }
    const sessionData = await res.json();
    await saveSession(sessionData);
    onLoginSuccess(sessionData);
    setLoading(false);
  };

  const submitCustomerRegistration = async (phone, token) => {
    const res = await fetch(`${BACKEND_URL}/api/auth/register-customer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phone,
        firebase_id_token: token,
        customer_name: customerName || null,
      }),
    });
    if (!res.ok) {
      const detail = await res.json();
      const msg = detail.detail || 'Registration failed';
      if (res.status === 400 || msg.includes('already exists')) {
        setSuggestLogin(true);
        throw new Error('Account already exists. Please log in.');
      }
      throw new Error(msg);
    }
    const sessionData = await res.json();
    await saveSession(sessionData);
    onLoginSuccess(sessionData);
    setLoading(false);
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.heroSection}>
          <Feather name="shopping-cart" size={48} color="#fff" />
          <Text style={styles.heroTitle}>RetailAutomate</Text>
          <Text style={styles.heroSubtitle}>AI-Powered Retail Management</Text>
        </View>


        <View style={styles.card}>
          <Text style={[sharedStyles.title, { marginBottom: 4, textAlign: 'center' }]}>
            Welcome Back
          </Text>
          <Text style={[sharedStyles.subtitle, { textAlign: 'center', marginBottom: 20 }]}>
            Select your role and sign in with phone
          </Text>

          {/* Role Selector */}
          <View style={styles.roleRow}>
            <TouchableOpacity
              style={[styles.roleBtn, role === 'customer' && styles.roleBtnActive]}
              onPress={() => handleRoleChange('customer')}
            >
              <Text style={[styles.roleBtnText, role === 'customer' && styles.roleBtnTextActive]}>
                👨‍💼 Customer
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.roleBtn, role === 'owner' && styles.roleBtnActive]}
              onPress={() => handleRoleChange('owner')}
            >
              <Text style={[styles.roleBtnText, role === 'owner' && styles.roleBtnTextActive]}>
                🏪 Shop Owner
              </Text>
            </TouchableOpacity>
          </View>

          {/* Customer auth mode toggle */}
          {role === 'customer' && (
            <View style={styles.modeRow}>
              <TouchableOpacity
                style={[styles.modeBtn, authMode === 'login' && styles.modeBtnActive]}
                onPress={() => handleModeChange('login')}
              >
                <Text style={[styles.modeBtnText, authMode === 'login' && styles.modeBtnTextActive]}>
                  Login
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modeBtn, authMode === 'register' && styles.modeBtnActive]}
                onPress={() => handleModeChange('register')}
              >
                <Text style={[styles.modeBtnText, authMode === 'register' && styles.modeBtnTextActive]}>
                  Create Account
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Owner register banner */}
          {role === 'owner' && (
            <View style={sharedStyles.infoBox}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={{ color: colors.primary, fontWeight: '600', fontSize: 13 }}>
                  New shop owner?
                </Text>
                <TouchableOpacity
                  onPress={() => navigation.navigate('OwnerRegister', { phoneNumber })}
                  style={{ borderWidth: 1, borderColor: colors.primary, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4 }}
                >
                  <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 12 }}>Register</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Error display */}
          {error && (
            <View style={sharedStyles.errorBox}>
              <Text style={sharedStyles.errorText}>{error}</Text>
              {suggestRegistration && (
                <TouchableOpacity
                  style={[sharedStyles.btnDanger, { marginTop: 8 }]}
                  onPress={() => {
                    resetState();
                    if (role === 'customer') {
                      handleModeChange('register');
                    } else {
                      navigation.navigate('OwnerRegister', { phoneNumber });
                    }
                  }}
                >
                  <Text style={sharedStyles.btnDangerText}>Create New Account</Text>
                </TouchableOpacity>
              )}
              {suggestLogin && (
                <TouchableOpacity
                  style={[sharedStyles.btnPrimary, { marginTop: 8 }]}
                  onPress={() => { resetState(); handleModeChange('login'); }}
                >
                  <Text style={sharedStyles.btnPrimaryText}>Go to Login</Text>
                </TouchableOpacity>
              )}
            </View>
          )}

          {/* Info display */}
          {infoMsg ? (
            <View style={sharedStyles.infoBox}>
              <Text style={sharedStyles.infoText}>{infoMsg}</Text>
            </View>
          ) : null}

          {!confirmationResult ? (
            <>
              {/* Customer register name field */}
              {role === 'customer' && authMode === 'register' && (
                <View>
                  <Text style={sharedStyles.label}>Full Name *</Text>
                  <TextInput
                    style={sharedStyles.input}
                    placeholder="John Doe"
                    value={customerName}
                    onChangeText={setCustomerName}
                    autoCapitalize="words"
                  />
                </View>
              )}

              <Text style={sharedStyles.label}>Phone Number *</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="+919876543210"
                value={phoneNumber}
                onChangeText={setPhoneNumber}
                keyboardType="phone-pad"
                autoComplete="tel"
              />

              <TouchableOpacity
                style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
                onPress={handleSendOtp}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={sharedStyles.btnPrimaryText}>Send OTP via SMS</Text>}
              </TouchableOpacity>
            </>
          ) : (
            <>
              {/* OTP verification */}
              <Text style={sharedStyles.label}>Enter 6-Digit Verification Code *</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="123456"
                value={otp}
                onChangeText={setOtp}
                keyboardType="number-pad"
                maxLength={6}
              />

              <TouchableOpacity
                style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
                onPress={handleVerifyOtp}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={sharedStyles.btnPrimaryText}>
                      {role === 'customer' && authMode === 'register'
                        ? 'Verify OTP & Create Account'
                        : 'Verify OTP & Login'}
                    </Text>}
              </TouchableOpacity>

              <TouchableOpacity
                style={sharedStyles.btnSecondary}
                onPress={() => { setConfirmationResult(null); setOtp(''); resetState(); }}
              >
                <Text style={sharedStyles.btnSecondaryText}>Change Phone Number</Text>
              </TouchableOpacity>
            </>
          )}

          {/* Developer bypass */}
          <View style={styles.bypassSection}>
            <View style={sharedStyles.divider} />
            <Text style={[sharedStyles.smallText, { textAlign: 'center', marginBottom: 8 }]}>
              🔧 Testing without Firebase configured?
            </Text>
            <TouchableOpacity
              style={[sharedStyles.btnSecondary, loading && sharedStyles.btnDisabled]}
              onPress={handleBypassLogin}
              disabled={loading}
            >
              {loading
                ? <ActivityIndicator color={colors.primary} />
                : <Text style={sharedStyles.btnSecondaryText}>Developer Login Bypass (Free)</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: colors.headerBg,
  },
  heroSection: {
    alignItems: 'center',
    paddingTop: 60,
    paddingBottom: 30,
    paddingHorizontal: 20,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: '900',
    color: '#fff',
    marginTop: 12,
  },
  heroSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 24,
    flex: 1,
    minHeight: 500,
  },
  roleRow: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceLight,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    marginBottom: 16,
    padding: 4,
    gap: 4,
  },
  roleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: radius.sm - 2,
    alignItems: 'center',
  },
  roleBtnActive: {
    backgroundColor: colors.primary,
  },
  roleBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  roleBtnTextActive: {
    color: '#fff',
  },
  modeRow: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceLight,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    marginBottom: 16,
    padding: 4,
    gap: 4,
  },
  modeBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.sm - 2,
    alignItems: 'center',
  },
  modeBtnActive: {
    backgroundColor: colors.primary,
  },
  modeBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  modeBtnTextActive: {
    color: '#fff',
  },
  bypassSection: {
    marginTop: 16,
  },
});
