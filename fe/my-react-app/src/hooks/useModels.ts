import { useEffect, useState } from 'react';
import type { ModelOption } from '../types/model';
import { fetchModels } from '../services/api';

export function useModels() {
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('cross_weighted');

  useEffect(() => {
    const loadModels = async () => {
      try {
        const { ok, result } = await fetchModels();
        if (!ok) return;
        const list = result.data?.models ?? [];
        const bestModel = list.find(model => model.id === 'cross_weighted');
        const choices = bestModel ? [bestModel] : [];
        setModelOptions(choices);
        setSelectedModel('cross_weighted');
      } catch {
        // Im lặng
      }
    };
    loadModels();
  }, []);

  return { modelOptions, selectedModel, setSelectedModel };
}
