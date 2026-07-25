import { env } from '../config/env';
export const apiClient = { baseUrl: env.apiBaseUrl, timeout: 10_000 } as const;
