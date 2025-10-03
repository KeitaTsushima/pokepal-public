import axios from 'axios';

// Timeout setting (P0: Quality gate requirement)
const DEFAULT_TIMEOUT = 10000; // 10 seconds = 10,000 milliseconds

// Create axios instance
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'https://pokepal-device-status-api.azurewebsites.net',
  timeout: DEFAULT_TIMEOUT,
});

// Record request start time for latency measurement
apiClient.interceptors.request.use((config) => {
  config.metadata = { startTime: Date.now() };
  // Phase 5: Add authentication token
  // if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor for success and error handling
apiClient.interceptors.response.use(
  (response) => {
    // Success: Log metrics
    console.info('[API Success]', {
      method: response.config.method,
      url: response.config.url,
      status: response.status,
      duration: Date.now() - response.config.metadata.startTime
    });
    return response;
  },
  (error) => {
    // Error: Classify errors
    if (error.response) {
      console.error('[API Error]', {
        method: error.config?.method,
        url: error.config?.url,
        status: error.response.status,
        // P0: Do not log response data (PII protection)
      });

      // Error vocabulary mapping (quality-rules.md compliant)
      if (error.response.status === 404) {
        error.domainError = 'NotFound';
      } else if (error.response.status === 503) {
        error.domainError = 'ServiceUnavailable';
      }
      // Phase 2: Add 429 handling
    } else if (error.code === 'ECONNABORTED') {
      error.domainError = 'Timeout';
    }

    return Promise.reject(error);
  }
);

export default apiClient;
