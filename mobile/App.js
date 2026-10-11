import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { View, ActivityIndicator } from 'react-native';

import { loadSession, clearSession } from './utils/storage';
import { colors } from './styles/theme';
import LoginScreen from './screens/LoginScreen';
import OwnerRegisterScreen from './screens/OwnerRegisterScreen';
import CustomerChatScreen from './screens/CustomerChatScreen';
import OwnerDashboardScreen from './screens/OwnerDashboardScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load persisted session on startup
  useEffect(() => {
    const restoreSession = async () => {
      const stored = await loadSession();
      if (stored) setSession(stored);
      setLoading(false);
    };
    restoreSession();
  }, []);

  const handleLoginSuccess = (userSession) => {
    setSession(userSession);
  };

  const handleLogout = async () => {
    await clearSession();
    setSession(null);
  };

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.headerBg }}>
        <ActivityIndicator size="large" color={colors.primary} />
        <StatusBar style="light" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!session ? (
          // ── Auth Stack ──
          <>
            <Stack.Screen name="Login">
              {(props) => (
                <LoginScreen
                  {...props}
                  onLoginSuccess={handleLoginSuccess}
                />
              )}
            </Stack.Screen>
            <Stack.Screen name="OwnerRegister">
              {(props) => (
                <OwnerRegisterScreen
                  {...props}
                  onLoginSuccess={handleLoginSuccess}
                />
              )}
            </Stack.Screen>
          </>
        ) : session.role === 'owner' ? (
          // ── Owner Dashboard ──
          <Stack.Screen name="OwnerDashboard">
            {(props) => (
              <OwnerDashboardScreen
                {...props}
                session={session}
                onLogout={handleLogout}
              />
            )}
          </Stack.Screen>
        ) : (
          // ── Customer Chat ──
          <Stack.Screen name="CustomerChat">
            {(props) => (
              <CustomerChatScreen
                {...props}
                session={session}
                onLogout={handleLogout}
              />
            )}
          </Stack.Screen>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
