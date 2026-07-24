import axios from 'axios';

const api = axios.create({
  withCredentials: true,
  xsrfCookieName: 'csrf_token',
  xsrfHeaderName: 'X-CSRF-Token',
});

export default api;
