import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

// Firebase configuration. Uses import.meta.env which Vite reads from frontend .env file.
const firebaseConfig = {
  apiKey: "AIzaSyB2vbJYy2ui5ZmtT1LKNeBXSVJu32CpLLM",
  authDomain: "retail-automation-project.firebaseapp.com",
  projectId: "retail-automation-project",
  storageBucket: "retail-automation-project.firebasestorage.app",
  messagingSenderId: "262766987503",
  appId: "1:262766987503:web:58cfe3d101684b5bf2331a"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
