import { useState, type FormEvent } from 'react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

interface ForgotPasswordProps {
  onBackToLogin: () => void;
}

function validateNewPassword(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters';
  if (!/[A-Z]/.test(password)) return 'Password must contain an uppercase letter';
  if (!/[a-z]/.test(password)) return 'Password must contain a lowercase letter';
  if (!/\d/.test(password)) return 'Password must contain a number';
  if (!/[^A-Za-z0-9]/.test(password)) return 'Password must contain a special character';
  return null;
}

export default function ForgotPassword({ onBackToLogin }: ForgotPasswordProps) {
  const { requestPasswordReset, resetPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [step, setStep] = useState<'request' | 'reset' | 'complete'>('request');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const requestOtp = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (!email.trim()) {
      setError('Please enter your email address');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await requestPasswordReset(email.trim());
      setMessage(result.message);
      setStep('reset');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Cannot request a reset code');
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitNewPassword = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (!/^\d{6}$/.test(otp)) {
      setError('Enter the 6-digit reset code');
      return;
    }

    const passwordError = validateNewPassword(newPassword);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPassword(email.trim(), otp, newPassword);
      setStep('complete');
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : 'Cannot reset password');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resendOtp = async () => {
    setError('');
    setMessage('');
    setIsSubmitting(true);
    try {
      const result = await requestPasswordReset(email.trim());
      setOtp('');
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Cannot request a new reset code');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderAlert = () => (
    <>
      {error && <div className="error-message" role="alert">{error}</div>}
      {message && <div className="success-message" role="status">{message}</div>}
    </>
  );

  return (
    <div className="auth-container">
      <div className="auth-form-side">
        <div className="auth-card">
          {step === 'request' && (
            <>
              <div className="auth-header">
                <h2>Forgot password?</h2>
                <p>Enter your email and we will issue a password reset code.</p>
              </div>

              <form onSubmit={requestOtp} className="auth-form">
                {renderAlert()}
                <div className="input-group">
                  <label htmlFor="reset-email">Email</label>
                  <div className="input-wrapper">
                    <input
                      type="email"
                      id="reset-email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@example.com"
                      autoComplete="email"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <button type="submit" className="submit-button" disabled={isSubmitting}>
                  {isSubmitting ? 'Sending code...' : 'Send reset code'}
                </button>
              </form>
            </>
          )}

          {step === 'reset' && (
            <>
              <div className="auth-header">
                <h2>Set a new password</h2>
                <p>Enter the reset code sent for {email}.</p>
              </div>

              <form onSubmit={submitNewPassword} className="auth-form">
                {renderAlert()}

                <div className="input-group">
                  <label htmlFor="reset-otp">Reset code</label>
                  <div className="input-wrapper">
                    <input
                      type="text"
                      id="reset-otp"
                      value={otp}
                      onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      placeholder="6-digit code"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label htmlFor="new-password">New password</label>
                  <div className="input-wrapper">
                    <input
                      type="password"
                      id="new-password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      autoComplete="new-password"
                      placeholder="At least 8 characters"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label htmlFor="confirm-new-password">Confirm new password</label>
                  <div className="input-wrapper">
                    <input
                      type="password"
                      id="confirm-new-password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      autoComplete="new-password"
                      placeholder="Re-enter your new password"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <button type="submit" className="submit-button" disabled={isSubmitting}>
                  {isSubmitting ? 'Updating password...' : 'Update password'}
                </button>

                <button type="button" className="text-button" onClick={resendOtp} disabled={isSubmitting}>
                  Resend reset code
                </button>
              </form>
            </>
          )}

          {step === 'complete' && (
            <div className="auth-form completion-panel">
              <div className="auth-header">
                <h2>Password updated</h2>
                <p>Your password has been changed successfully. You can now sign in.</p>
              </div>
              <button type="button" className="submit-button" onClick={onBackToLogin}>
                Back to sign in
              </button>
            </div>
          )}

          {step !== 'complete' && (
            <div className="auth-footer">
              <p>
                Remember your password?{' '}
                <a href="#login" onClick={(event) => { event.preventDefault(); onBackToLogin(); }}>
                  Sign in
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
