import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

const firebaseConfig = {
  apiKey: "AIzaSyBn4bBPCDnRfvUxkE5Kww9U62q5ZjdFE-k",
  authDomain: "django-f09c1.firebaseapp.com",
  projectId: "django-f09c1",
  storageBucket: "django-f09c1.firebasestorage.app",
  messagingSenderId: "544816611144",
  appId: "1:544816611144:web:2c5a9bc6f0f3a0ef027d7d",
  measurementId: "G-VQK3Z3LG00"
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export default app