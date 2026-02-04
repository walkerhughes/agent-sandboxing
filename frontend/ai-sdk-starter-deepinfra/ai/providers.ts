import { openai } from "@ai-sdk/openai";

// Language model configurations
const languageModels = {
  "gpt-5-nano": "gpt-5-nano",
  "gpt-4o": "gpt-4o",
  "gpt-4o-mini": "gpt-4o-mini",
} as const;

export type modelID = keyof typeof languageModels;

export const MODELS = Object.keys(languageModels) as modelID[];

export const defaultModel: modelID = "gpt-5-nano";

// Helper to get a language model instance
export function getModel(modelId: modelID) {
  return openai(languageModels[modelId]);
}

// For backwards compatibility with existing code that uses model.languageModel()
export const model = {
  languageModel: (modelId: modelID) => openai(languageModels[modelId]),
};
