import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyCHtYB1jvEfGFX8RZ8ioQ5mIZFHot7YDpk",
  authDomain: "sensex-edge-telugu.firebaseapp.com",
  projectId: "sensex-edge-telugu",
  storageBucket: "sensex-edge-telugu.firebasestorage.app",
  messagingSenderId: "102184552364",
  appId: "1:102184552364:web:19623a9797cac30da6dc09",
};

const app = initializeApp(firebaseConfig);

export const db = getFirestore(app);