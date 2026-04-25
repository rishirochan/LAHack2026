export const MOCK_AUTH_STORAGE_KEY = 'eloquence.mock-auth-user';

export const MOCK_LOGIN_CREDENTIALS = {
  email: 'demo@eloquence.ai',
  password: 'portfolio-demo',
} as const;

export interface MockUser {
  email: string;
  loggedInAt: string;
}

export function isValidMockLogin(email: string, password: string) {
  return (
    email.trim().toLowerCase() === MOCK_LOGIN_CREDENTIALS.email &&
    password === MOCK_LOGIN_CREDENTIALS.password
  );
}

export function createMockUser(email: string): MockUser {
  return {
    email: email.trim().toLowerCase(),
    loggedInAt: new Date().toISOString(),
  };
}
