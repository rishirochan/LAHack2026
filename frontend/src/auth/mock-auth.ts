export const MOCK_AUTH_STORAGE_KEY = 'clarity.mock-auth-user';

export const MOCK_LOGIN_CREDENTIALS = {
  email: 'demo@clarity.ai',
  password: 'demo',
} as const;

export interface MockUser {
  fullName: string;
  email: string;
  loggedInAt: string;
}

export function isValidMockLogin(email: string, password: string) {
  return (
    email.trim().toLowerCase() === MOCK_LOGIN_CREDENTIALS.email &&
    password === MOCK_LOGIN_CREDENTIALS.password
  );
}

export function createMockUser(fullName: string, email: string): MockUser {
  return {
    fullName: fullName.trim() || 'Demo User',
    email: email.trim().toLowerCase(),
    loggedInAt: new Date().toISOString(),
  };
}
