import { http } from './client.js';

const RESOURCE = '/rules/deadline-extensions';

export const ruleApi = {
  list: () => http.get(RESOURCE),
  create: (payload) => http.post(RESOURCE, payload),
};
