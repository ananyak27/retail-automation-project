
import { initializeApp, getApps } from 'firebase/app';
import {
  getAuth,
  initializeAuth,
  getReactNativePersistence,
} from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

const firebaseConfig = {
  apiKey: 'AIzaSyB2vbJYy2ui5ZmtT1LKNeBXSVJu32CpLLM',
  authDomain: 'retail-automation-project.firebaseapp.com',
  projectId: 'retail-automation-project',
  storageBucket: 'retail-automation-project.firebasestorage.app',
  messagingSenderId: '262766987503',
  appId: '1:262766987503:web:58cfe3d101684b5bf2331a',
};

const app = getApps().length === 0
  ? initializeApp(firebaseConfig)
  : getApps()[0];

let auth;

try {
  auth = initializeAuth(app, {
    persistence: getReactNativePersistence(AsyncStorage),
  });
} catch (error) {
  // Reuse existing Auth instance during reloads.
  auth = getAuth(app);
}

export { auth };

export const FIREBASE_PROJECT_ID = 'retail-automation-project';

export const BACKEND_URL =
  'https://retail-automation-project.onrender.com';

export const getWebSocketUrl = (backendUrl, userId) => {
  const wsProtocol = backendUrl.startsWith('https://')
    ? 'wss:'
    : 'ws:';

  const host = backendUrl.replace(/^https?:\/\//, '');

  return `${wsProtocol}//${host}/ws/${userId}`;
};
