import { useCallback, useState } from 'react';

export function useNotify(autoCloseMs: number = 3000) {
  const [notification, setNotification] = useState<string | null>(null);

  const showNotify = useCallback((msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), autoCloseMs);
  }, [autoCloseMs]);

  return { notification, showNotify };
}
