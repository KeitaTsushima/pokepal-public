import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
  type AxiosError,
} from 'axios'

// Extend AxiosRequestConfig to include metadata
interface RequestConfigWithMetadata extends InternalAxiosRequestConfig {
  metadata?: {
    startTime: number
  }
}

// Extend AxiosError to include domainError
interface DomainAxiosError extends AxiosError {
  domainError?: 'NotFound' | 'ServiceUnavailable' | 'Timeout' | 'NetworkError'
}

// Timeout setting (P0: Quality gate requirement)
const DEFAULT_TIMEOUT = 10000 // 10 seconds = 10,000 milliseconds

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL || 'https://pokepal-device-status-api.azurewebsites.net',
  timeout: DEFAULT_TIMEOUT,
})

// Record request start time for latency measurement
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): RequestConfigWithMetadata => {
    const configWithMetadata = config as RequestConfigWithMetadata
    configWithMetadata.metadata = { startTime: Date.now() }
    // Phase 5: Add authentication token
    // if (token) config.headers.Authorization = `Bearer ${token}`;
    return configWithMetadata
  }
)

// Response interceptor for success and error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => {
    // Success: Log metrics
    const config = response.config as RequestConfigWithMetadata
    const duration = config.metadata?.startTime ? Date.now() - config.metadata.startTime : null
    // TODO: Sanitize URL to prevent PII leakage (query params, path segments)
    // TODO: Replace console.info with structured logger
    console.info('[API Success]', {
      method: config.method,
      url: config.url,
      status: response.status,
      duration,
    })
    return response
  },
  (error: AxiosError): Promise<never> => {
    const domainError = error as DomainAxiosError
    const config = domainError.config as RequestConfigWithMetadata | undefined
    const duration = config?.metadata?.startTime ? Date.now() - config.metadata.startTime : null

    // Error: Classify errors
    if (domainError.response) {
      // TODO: Sanitize URL to prevent PII leakage (query params, path segments)
      // TODO: Replace console.error with structured logger
      console.error('[API Error]', {
        method: config?.method,
        url: config?.url,
        status: domainError.response.status,
        duration,
        // P0: Do not log response data (PII protection)
      })

      // Error vocabulary mapping (quality-rules.md compliant)
      if (domainError.response.status === 404) {
        domainError.domainError = 'NotFound'
      } else if (domainError.response.status === 503) {
        domainError.domainError = 'ServiceUnavailable'
      }
      // TODO: Add more status code mappings (400→ValidationError, 401→Unauthorized, 403→Forbidden, 500/502→ServerError)
      // TODO: Add 429 (rate limit) handling with retry logic
    } else if (domainError.code === 'ECONNABORTED') {
      domainError.domainError = 'Timeout'
    } else {
      // Network errors: DNS, connection refused, etc.
      domainError.domainError = 'NetworkError'
      console.error('[API Network Error]', {
        method: config?.method,
        url: config?.url,
        code: domainError.code,
        message: domainError.message,
        duration,
      })
    }

    return Promise.reject(domainError)
  }
)

export default apiClient
