import { http } from './client.js';

export const assessmentApi = {
  list: (params) => http.get('/assessments', params),
  generate: (month, operator) => http.post('/assessments/generate', { month, operator }),
};
