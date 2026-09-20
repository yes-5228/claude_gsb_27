import { http } from './client.js';

export const ruleApi = {
  list: () => http.get('/deadline-rules'),
  create: (payload) => http.post('/deadline-rules', payload),
  update: (id, payload) => http.patch(`/deadline-rules/${id}`, payload),
};
