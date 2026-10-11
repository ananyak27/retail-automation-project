// Firebase JS SDK configuration (same credentials as the web app)
// This works in Expo Go without any native setup or google-services.json
import { initializeApp, getApps } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: 'AIzaSyB2vbJYy2ui5ZmtT1LKNeBXSVJu32CpLLM',
  authDomain: 'retail-automation-project.firebaseapp.com',
  projectId: 'retail-automation-project',
  storageBucket: 'retail-automation-project.firebasestorage.app',
  messagingSenderId: '262766987503',
  appId: '1:262766987503:web:58cfe3d101684b5bf2331a',
};

// Avoid re-initializing on hot reload
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
export const FIREBASE_PROJECT_ID = 'retail-automation-project';

// ─── Backend URL ───────────────────────────────────────────────────────────────
// Change this to your FastAPI backend IP (same Wi-Fi network as phone)
// Run `ipconfig` on your PC and use the IPv4 address shown
export const BACKEND_URL = 'http://192.168.1.105:8000';

export const getWebSocketUrl = (backendUrl, userId) => {
  const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
  const host = backendUrl.replace(/^https?:\/\//, '');
  return `${wsProtocol}//${host}/ws/${userId}`;
};
