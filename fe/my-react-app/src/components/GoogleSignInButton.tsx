import { useEffect, useRef } from 'react';
import { loadGoogleIdentityScript, useAuth } from '../context/AuthContext';

interface GoogleSignInButtonProps {
  disabled?: boolean;
  onError: (message: string) => void;
  onStart: () => void;
  onFinish: () => void;
}

export default function GoogleSignInButton({
  disabled = false,
  onError,
  onStart,
  onFinish,
}: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const { getGoogleClientId, loginWithGoogleCredential } = useAuth();

  useEffect(() => {
    let isMounted = true;

    const renderGoogleButton = async () => {
      try {
        const clientId = await getGoogleClientId();
        await loadGoogleIdentityScript();

        if (!isMounted || !buttonRef.current || !window.google?.accounts?.id) return;

        buttonRef.current.innerHTML = '';
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response) => {
            if (!response.credential) {
              onError('Google did not return an id_token');
              return;
            }

            onStart();
            try {
              await loginWithGoogleCredential(response.credential);
            } catch (error) {
              onError(error instanceof Error ? error.message : 'Cannot continue with Google');
            } finally {
              onFinish();
            }
          },
        });

        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'rectangular',
          width: buttonRef.current.clientWidth || 380,
        });
      } catch (error) {
        onError(error instanceof Error ? error.message : 'Cannot load Google Sign-In');
      }
    };

    void renderGoogleButton();

    return () => {
      isMounted = false;
    };
  }, [getGoogleClientId, loginWithGoogleCredential, onError, onFinish, onStart]);

  return (
    <div className={`google-rendered-button ${disabled ? 'disabled' : ''}`}>
      <div ref={buttonRef} />
    </div>
  );
}
