import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';
const AUTH_STORAGE_KEY = 'aip491_auth';

interface GoogleCredentialResponse {
  credential?: string;
}

interface GoogleAccounts {
  accounts: {
    id: {
      initialize: (options: {
        client_id: string;
        callback: (response: GoogleCredentialResponse) => void;
      }) => void;
      renderButton: (
        parent: HTMLElement,
        options: {
          theme?: 'outline' | 'filled_blue' | 'filled_black';
          size?: 'large' | 'medium' | 'small';
          text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
          shape?: 'rectangular' | 'pill' | 'circle' | 'square';
          width?: number;
        },
      ) => void;
      prompt: () => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleAccounts;
  }
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

interface GoogleClientConfigResponse {
  client_id: string;
}

interface CurrentUserResponse {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  auth_provider: string;
}

interface ForgotPasswordResponse {
  status: string;
  message: string;
}

interface StoredAuth {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

interface AuthUser {
  email: string;
  name: string;
  username?: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: AuthUser | null;
  accessToken: string | null;
  login: (username: string, password: string) => Promise<void>;
  signup: (name: string, username: string, email: string, password: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  loginWithGoogleCredential: (idToken: string) => Promise<void>;
  getGoogleClientId: () => Promise<string>;
  requestPasswordReset: (email: string) => Promise<{ message: string }>;
  resetPassword: (email: string, otp: string, newPassword: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function readStoredAuth(): StoredAuth | null {
  const rawValue = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!rawValue) return null;

  try {
    const parsed = JSON.parse(rawValue) as StoredAuth;
    if (!parsed.accessToken || !parsed.refreshToken || !parsed.user) return null;
    const repairedName = repairMojibake(parsed.user.name);
    if (repairedName !== parsed.user.name) {
      parsed.user.name = repairedName;
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(parsed));
    }
    return parsed;
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(', ') || 'Request failed';
    }
  } catch {
    // Fall through to status text.
  }

  return response.statusText || 'Request failed';
}

async function postJson<TResponse>(
  path: string,
  body: unknown,
  accessToken?: string | null,
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<TResponse>;
}

async function getJson<TResponse>(path: string, accessToken?: string | null): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Accept': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<TResponse>;
}

async function getGoogleClientId(): Promise<string> {
  if (GOOGLE_CLIENT_ID) return GOOGLE_CLIENT_ID;

  const config = await getJson<GoogleClientConfigResponse>('/api/auth/google-client-id');
  if (!config.client_id) {
    throw new Error('Google Sign-In is not configured');
  }

  return config.client_id;
}

function decodeJwtPayload<TPayload>(token: string): TPayload | null {
  try {
    const [, payload] = token.split('.');
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '='));
    const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
    const decoded = new TextDecoder('utf-8').decode(bytes);
    return JSON.parse(decoded) as TPayload;
  } catch {
    return null;
  }
}

function repairMojibake(value: string): string {
  if (!/[ÃÂÄÅ]/.test(value)) return value;

  try {
    const bytes = Uint8Array.from(value, char => char.charCodeAt(0) & 0xff);
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch {
    return value;
  }
}

async function getCurrentUser(accessToken: string): Promise<AuthUser> {
  const profile = await getJson<CurrentUserResponse>('/api/auth/me', accessToken);
  return {
    email: profile.email,
    name: repairMojibake(profile.full_name),
    username: profile.username,
  };
}

export function loadGoogleIdentityScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );

    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener('error', () => reject(new Error('Cannot load Google Sign-In')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Cannot load Google Sign-In'));
    document.head.appendChild(script);
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<StoredAuth | null>(() => readStoredAuth());

  useEffect(() => {
    const accessToken = auth?.accessToken;
    if (!accessToken) return;

    let active = true;
    void getCurrentUser(accessToken)
      .then((user) => {
        if (!active) return;
        setAuth((currentAuth) => {
          if (!currentAuth) return null;
          const refreshedAuth = { ...currentAuth, user };
          localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(refreshedAuth));
          return refreshedAuth;
        });
      })
      .catch(() => {
        // Keep the existing session display if the profile API is temporarily unavailable.
      });

    return () => {
      active = false;
    };
  }, [auth?.accessToken]);

  const saveAuth = (tokens: TokenResponse, user: AuthUser) => {
    const nextAuth: StoredAuth = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      user,
    };

    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextAuth));
    setAuth(nextAuth);
  };

  const login = async (username: string, password: string) => {
    const tokens = await postJson<TokenResponse>('/api/auth/login', {
      username,
      password,
    });

    const user = await getCurrentUser(tokens.access_token);
    saveAuth(tokens, user);
  };

  const signup = async (name: string, username: string, email: string, password: string) => {
    await postJson('/api/auth/register', {
      username,
      email,
      password,
      full_name: name,
    });

    const tokens = await postJson<TokenResponse>('/api/auth/login', {
      username,
      password,
    });

    const user = await getCurrentUser(tokens.access_token);
    saveAuth(tokens, user);
  };

  const loginWithGoogleCredential = async (idToken: string) => {
    const tokens = await postJson<TokenResponse>('/api/auth/google', {
      id_token: idToken,
    });
    const googleProfile = decodeJwtPayload<{ email?: string; name?: string }>(idToken);
    try {
      saveAuth(tokens, await getCurrentUser(tokens.access_token));
    } catch {
      saveAuth(tokens, {
        email: googleProfile?.email ?? 'google-user',
        name: repairMojibake(googleProfile?.name ?? googleProfile?.email ?? 'Google User'),
      });
    }
  };

  const loginWithGoogle = async () => {
    throw new Error('Google Sign-In is loading. Please use the Google button again.');
  };

  const requestPasswordReset = async (email: string) => {
    const response = await postJson<ForgotPasswordResponse>('/api/auth/forgot-password', { email });
    return {
      message: response.message,
    };
  };

  const resetPassword = async (email: string, otp: string, newPassword: string) => {
    await postJson('/api/auth/reset-password', {
      email,
      otp,
      new_password: newPassword,
    });
  };

  const logout = async () => {
    const currentAuth = auth;

    localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuth(null);

    if (!currentAuth?.accessToken) return;

    try {
      await postJson(
        '/api/auth/logout',
        { refresh_token: currentAuth.refreshToken },
        currentAuth.accessToken,
      );
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <AuthContext.Provider 
      value={{ 
        isAuthenticated: !!auth, 
        user: auth?.user ?? null,
        accessToken: auth?.accessToken ?? null,
        login, 
        signup,
        loginWithGoogle,
        loginWithGoogleCredential,
        getGoogleClientId,
        requestPasswordReset,
        resetPassword,
        logout 
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
