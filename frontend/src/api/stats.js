import { http } from './client.js';

export const statsApi = {
  overview: () => http.get('/stats/overview'),
  dashboard: (trendDays = 14) => http.get('/stats/dashboard', { trend_days: trendDays }),
  assessments: (params) => http.get('/stats/assessments', params),
  assessmentMonths: () => http.get('/stats/assessments/months'),
  generateAssessments: (yearMonth) => http.post('/stats/assessments/generate', { year_month: yearMonth }),
};
