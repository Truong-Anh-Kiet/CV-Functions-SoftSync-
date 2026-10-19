import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import GoogleSignInButton from './GoogleSignInButton';
import './Login.css'; // Dùng chung file CSS đã sửa lúc nãy

interface SignupProps {
  onSwitchToLogin: () => void;
}

export default function Signup({ onSwitchToLogin }: SignupProps) {
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signup } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!fullName || !username || !email || !password || !confirmPassword) {
      setError('Please fill in all fields');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);
    try {
      await signup(fullName, username, email, password);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Cannot create account');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      {/* Khung Form đã được đưa ra giữa nhờ CSS */}
      <div className="auth-form-side">
        <div className="auth-card">
          <div className="auth-header">
            <h2>Create Account</h2>
            <p>Sign up to get started with JD Match</p>
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
              <label htmlFor="fullName">Full Name</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  id="fullName"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Enter your full name"
                  disabled={isSubmitting}
                />
                <svg viewBox="0 0 24 24">
                  <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                </svg>
              </div>
            </div>

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
              <label htmlFor="email">Email</label>
              <div className="input-wrapper">
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={isSubmitting}
                />
                <svg viewBox="0 0 24 24">
                  <path d="M3 7a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7zm2.4 0L12 12.25 18.6 7H5.4z"/>
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

            <div className="input-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  disabled={isSubmitting}
                />
                <svg viewBox="0 0 24 24">
                  <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                </svg>
              </div>
            </div>

            <button type="submit" className="submit-button" disabled={isSubmitting}>
              {isSubmitting ? 'Creating Account...' : 'Create Account'}
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
            <div className="switch-link">
              <span>Already have an account?</span>
              <a href="#" onClick={(e) => { e.preventDefault(); onSwitchToLogin(); }}>Sign in</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
