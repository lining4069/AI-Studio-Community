export type SessionMessage = {
  id?: string;
  role?: string;
  content?: string;
  created_at?: string;
};

export type SessionStep = {
  id?: string;
  step_index?: number;
  type?: string;
  name?: string;
  status?: string;
  output?: unknown;
  error?: string | null;
  created_at?: string;
};
