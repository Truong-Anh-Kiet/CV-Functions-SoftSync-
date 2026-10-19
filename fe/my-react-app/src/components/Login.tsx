import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import GoogleSignInButton from './GoogleSignInButton';
import './Login.css';

interface LoginProps {
  onSwitchToSignup: () => void;
  onForgotPassword: () => void;
}

export default function Login({ onSwitchToSignup, onForgotPassword }: LoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username || !password) {
      setError('Please fill in all fields');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(username, password);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Cannot sign in');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      {/* Form đăng nhập sẽ được đưa ra giữa */}
      <div className="auth-form-side">
        <div className="auth-card">
          <div className="auth-header">
            <h2>Welcome Back</h2>
            <p>Sign in to your account to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {error && (
              <div className="error-message">
                <svg viewBox="0 0 24 24">
                  <path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                {error}
              </div>
            )}

            <div className="input-group">
              <label htmlFor="username">Username</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  disabled={isSubmitting}
                />
                <svg viewBox="0 0 24 24">
                  <path d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"/>
                </svg>
              </div>
            </div>

            <div className="input-group">
              <label htmlFor="password">Password</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                  placeholder="••••••••••••"
                />
                <svg viewBox="0 0 24 24">
                  <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                </svg>
              </div>
            </div>

            <div className="form-options">
              <label className="remember-me">
                <input type="checkbox" />
                <span>Remember me</span>
              </label>
              <a
                href="#forgot-password"
                className="forgot-password"
                onClick={(event) => {
                  event.preventDefault();
                  onForgotPassword();
                }}
              >
                Forgot password?
              </a>
            </div>

            <button type="submit" className="submit-button" disabled={isSubmitting}>
              {isSubmitting ? 'Signing In...' : 'Sign In'}
            </button>

            <div className="auth-divider">
              <span>or continue with</span>
            </div>

            <GoogleSignInButton
              disabled={isSubmitting}
              onError={setError}
              onStart={() => {
                setError('');
                setIsSubmitting(true);
              }}
              onFinish={() => setIsSubmitting(false)}
            />
          </form>

          <div className="auth-footer">
            <p>Don't have an account? <a href="#" onClick={(e) => { e.preventDefault(); onSwitchToSignup(); }}>Sign up</a></p>
          </div>
        </div>
      </div>
    </div>
  );
}
