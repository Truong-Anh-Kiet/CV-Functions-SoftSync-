import { useEffect, useState } from 'react';
import type { ModelOption } from '../types/model';
import { fetchModels } from '../services/api';

export function useModels() {
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');

  useEffect(() => {
    const loadModels = async () => {
      try {
        const { ok, result } = await fetchModels();
        if (!ok) return;
        const list = result.data?.models ?? [];
        const fallback = result.data?.default ?? list[0]?.id ?? '';
        setModelOptions(list);
        setSelectedModel(prev => prev || fallback);
      } catch {
        // Im lặng
      }
    };
    loadModels();
  }, []);

  return { modelOptions, selectedModel, setSelectedModel };
}
