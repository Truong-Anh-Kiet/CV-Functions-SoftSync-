import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import Dashboard from './components/Dashboard';
import ForgotPassword from './components/ForgotPassword';

type AuthView = 'login' | 'signup' | 'forgot-password';

function AppContent() {
  const { isAuthenticated } = useAuth();
  const [authView, setAuthView] = useState<AuthView>('login');

  if (isAuthenticated) {
    return <Dashboard />;
  }

  if (authView === 'signup') {
    return <Signup onSwitchToLogin={() => setAuthView('login')} />;
  }

  if (authView === 'forgot-password') {
    return <ForgotPassword onBackToLogin={() => setAuthView('login')} />;
  }

  return (
    <Login
      onSwitchToSignup={() => setAuthView('signup')}
      onForgotPassword={() => setAuthView('forgot-password')}
    />
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
