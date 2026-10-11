import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import { saveSession } from '../utils/storage';
import { colors, sharedStyles, radius } from '../styles/theme';
import { BACKEND_URL } from '../firebaseConfig';

export default function OwnerRegisterScreen({ navigation, route, onLoginSuccess }) {
  const initialPhone = route?.params?.phoneNumber || '';

  const [step, setStep] = useState(1); // 1 = owner details, 2 = shop details
  const [ownerName, setOwnerName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState(initialPhone);
  const [shopName, setShopName] = useState('');
  const [shopAddress, setShopAddress] = useState('');
  const [shopCategory, setShopCategory] = useState('grocery');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMsg, setInfoMsg] = useState('');

  const cleanPhone = (p) => p.trim().replace(/\s+/g, '');

  const validateStep1 = () => {
    if (!ownerName.trim()) { setError('Please enter your full name.'); return false; }
    const phone = cleanPhone(phoneNumber);
    if (!phone.startsWith('+')) { setError('Phone must include country code (e.g. +919876543210)'); return false; }
    return true;
  };

  const handleNext = () => {
    setError(null);
    if (!validateStep1()) return;
    setStep(2);
  };

  const handleRegister = async () => {
    setError(null);
    if (!shopName.trim()) { setError('Please enter your shop name.'); return; }

    const phone = cleanPhone(phoneNumber);
    setLoading(true);

    try {
      // Step 1: Register owner
      const ownerRes = await fetch(`${BACKEND_URL}/api/auth/register-owner`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number: phone,
          firebase_id_token: 'mock_token_' + phone, // Replace with real token in production
          owner_name: ownerName.trim(),
          email: email.trim() || null,
        }),
      });

      if (!ownerRes.ok) {
        const detail = await ownerRes.json();
        throw new Error(detail.detail || 'Owner registration failed.');
      }

      const sessionData = await ownerRes.json();

      // Step 2: Create shop automatically
      if (shopName.trim()) {
        await fetch(`${BACKEND_URL}/api/shops/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${sessionData.access_token}`,
          },
          body: JSON.stringify({
            name: shopName.trim(),
            address: shopAddress.trim() || null,
            category: shopCategory,
          }),
        });
      }

      await saveSession(sessionData);
      onLoginSuccess(sessionData);
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Feather name="arrow-left" size={22} color="#fff" />
          </TouchableOpacity>
          <View style={{ alignItems: 'center', flex: 1 }}>
            <Feather name="store" size={36} color="#fff" />
            <Text style={styles.headerTitle}>Register as Shop Owner</Text>
            <Text style={styles.headerSubtitle}>Step {step} of 2</Text>
          </View>
          <View style={{ width: 36 }} />
        </View>

        <View style={styles.card}>
          {/* Step indicator */}
          <View style={styles.stepRow}>
            <View style={[styles.stepDot, step >= 1 && styles.stepDotActive]}>
              <Text style={styles.stepDotText}>1</Text>
            </View>
            <View style={[styles.stepLine, step >= 2 && styles.stepLineActive]} />
            <View style={[styles.stepDot, step >= 2 && styles.stepDotActive]}>
              <Text style={styles.stepDotText}>2</Text>
            </View>
          </View>

          {/* Error */}
          {error && (
            <View style={sharedStyles.errorBox}>
              <Text style={sharedStyles.errorText}>{error}</Text>
            </View>
          )}
          {infoMsg ? (
            <View style={sharedStyles.infoBox}>
              <Text style={sharedStyles.infoText}>{infoMsg}</Text>
            </View>
          ) : null}

          {step === 1 ? (
            <>
              <Text style={styles.sectionTitle}>Your Details</Text>

              <Text style={sharedStyles.label}>Full Name *</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="John Doe"
                value={ownerName}
                onChangeText={setOwnerName}
                autoCapitalize="words"
              />

              <Text style={sharedStyles.label}>Phone Number *</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="+919876543210"
                value={phoneNumber}
                onChangeText={setPhoneNumber}
                keyboardType="phone-pad"
              />

              <Text style={sharedStyles.label}>Email (Optional)</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="you@example.com"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />

              <TouchableOpacity style={sharedStyles.btnPrimary} onPress={handleNext}>
                <Text style={sharedStyles.btnPrimaryText}>Next: Shop Details →</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.sectionTitle}>Your Shop Details</Text>

              <Text style={sharedStyles.label}>Shop Name *</Text>
              <TextInput
                style={sharedStyles.input}
                placeholder="My Grocery Store"
                value={shopName}
                onChangeText={setShopName}
              />

              <Text style={sharedStyles.label}>Shop Address (Optional)</Text>
              <TextInput
                style={[sharedStyles.input, { height: 80, textAlignVertical: 'top' }]}
                placeholder="123 Main Street, City"
                value={shopAddress}
                onChangeText={setShopAddress}
                multiline
              />

              <Text style={sharedStyles.label}>Category</Text>
              <View style={styles.categoryRow}>
                {['grocery', 'pharmacy', 'electronics', 'clothing', 'other'].map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.catBtn, shopCategory === cat && styles.catBtnActive]}
                    onPress={() => setShopCategory(cat)}
                  >
                    <Text style={[styles.catBtnText, shopCategory === cat && styles.catBtnTextActive]}>
                      {cat}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity
                style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
                onPress={handleRegister}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={sharedStyles.btnPrimaryText}>🏪 Create My Shop & Register</Text>}
              </TouchableOpacity>

              <TouchableOpacity
                style={sharedStyles.btnSecondary}
                onPress={() => { setStep(1); setError(null); }}
              >
                <Text style={sharedStyles.btnSecondaryText}>← Back</Text>
              </TouchableOpacity>
            </>
          )}
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 56,
    paddingBottom: 28,
    paddingHorizontal: 20,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#fff',
    marginTop: 8,
  },
  headerSubtitle: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.6)',
    marginTop: 2,
  },
  card: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 24,
    flex: 1,
    minHeight: 500,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 16,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
    gap: 0,
  },
  stepDot: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.surfaceBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDotActive: {
    backgroundColor: colors.primary,
  },
  stepDotText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 13,
  },
  stepLine: {
    flex: 1,
    height: 3,
    backgroundColor: colors.surfaceBorder,
    marginHorizontal: 8,
  },
  stepLineActive: {
    backgroundColor: colors.primary,
  },
  categoryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  catBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    backgroundColor: colors.surfaceLight,
  },
  catBtnActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  catBtnText: {
    fontSize: 12,
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  catBtnTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
});
