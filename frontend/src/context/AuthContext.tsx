import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import type { User } from 'firebase/auth';
import { doc, getDoc, serverTimestamp, setDoc } from 'firebase/firestore';
import { auth, db } from '../config/firebase';

export type UserRole = 'admin' | 'driver';

interface UserProfile {
  email: string;
  role: UserRole;
  createdAt?: Date;
}

interface AuthContextValue {
  user: User | null;
  role: UserRole | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, role: UserRole) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUserRole = async (firebaseUser: User) => {
    try {
      const userDoc = await getDoc(doc(db, 'users', firebaseUser.uid));
      if (userDoc.exists()) {
        const data = userDoc.data() as UserProfile;
        console.log('Loaded user role:', data.role);
        // Admin chỉ được kích hoạt khi email đã verified
        if (data.role === 'admin') {
          setRole(firebaseUser.emailVerified ? 'admin' : 'driver');
        } else {
          setRole('driver');
        }
      } else {
        setRole('driver');
      }
    } catch (error) {
      console.error('Failed to load user role', error);
      setRole('driver');
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        await loadUserRole(firebaseUser);
      } else {
        setRole(null);
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const login = async (email: string, password: string) => {
    setLoading(true);
    const credential = await signInWithEmailAndPassword(auth, email, password);
    if (credential.user) {
      await loadUserRole(credential.user);
    }
    setLoading(false);
  };

  const register = async (email: string, password: string, selectedRole: UserRole) => {
    setLoading(true);
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    
    // Gửi email verification nếu đăng ký admin
    if (selectedRole === 'admin') {
      await sendEmailVerification(credential.user);
    }
    
    await setDoc(doc(db, 'users', credential.user.uid), {
      email,
      role: selectedRole,
      createdAt: serverTimestamp(),
    });
    
    // Admin chỉ được kích hoạt khi email đã verified
    setRole(credential.user.emailVerified ? selectedRole : 'driver');
    setLoading(false);
  };

  const logout = async () => {
    await signOut(auth);
    setRole(null);
  };

  return (
    <AuthContext.Provider value={{ user, role, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}

