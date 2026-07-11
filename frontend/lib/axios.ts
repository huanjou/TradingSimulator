import axios from 'axios';

const api = axios.create({
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  // Try to get CSRF token from cookies
  const match = document.cookie.match(/(?:^|;) ?csrf_token=([^;]*)(?:;|$)/);
  if (match && match[1]) {
    config.headers['X-CSRF-Token'] = match[1];
  }
  return config;
});

export default api;
