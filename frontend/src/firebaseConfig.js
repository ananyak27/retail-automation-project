import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

// Firebase configuration. Uses import.meta.env which Vite reads from frontend .env file.
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyPlaceholderAPIKeyForRetailAutomation",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "retail-automation-project.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "retail-automation-project",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "retail-automation-project.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "123456789",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:123456789:web:abcdef12345"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
