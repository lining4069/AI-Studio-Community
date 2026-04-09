import { create } from "zustand";

type ShellState = {
  knowledgeBaseSearch: string;
  agentSearch: string;
  setKnowledgeBaseSearch: (value: string) => void;
  setAgentSearch: (value: string) => void;
};

export const useShellStore = create<ShellState>((set) => ({
  knowledgeBaseSearch: "",
  agentSearch: "",
  setKnowledgeBaseSearch: (value) => set({ knowledgeBaseSearch: value }),
  setAgentSearch: (value) => set({ agentSearch: value }),
}));
