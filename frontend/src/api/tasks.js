import { http } from './client.js';

export const taskApi = {
  list: (params) => http.get('/inspection-tasks', params),
  generate: (taskDate) => http.post('/inspection-tasks/generate', { task_date: taskDate }),
};
