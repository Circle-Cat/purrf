/**
 * @fileoverview This module provides a pre-configured Axios instance for
 * consistent API request handling. It centralizes timeout settings, response
 * extraction, and error handling to simplify API interactions across the app.
 */

import axios from "axios";

/**
 * Pre-configured Axios instance for standardized API communication.
 *
 * Features:
 * - Default timeout: 10 seconds
 * - Includes credentials (cookies) in requests
 * - Centralized configuration for future customizations
 *
 * Environment behavior:
 * - Development: requests to `/api` are proxied to the local backend via the Vite dev server.
 * - Production (same domain/cluster): `/api` works directly.
 * - Production (different domain): `baseURL` can automatically point to the full backend URL.
 *      Example:
 *      const BASE_URL = import.meta.env.PROD
 *          ? "https://yourdomain.com/api"
 *          : "/api";
 *
 * Usage:
 * - Requests can use relative paths like `/users`, `/login`, etc.
 *
 * This instance ensures consistent timeout and provides a central place
 * to customize request behavior in the future.
 *
 * @type {import('axios').AxiosInstance}
 */
const request = axios.create({
  baseURL: import.meta.env.PROD
    ? import.meta.env.VITE_API_BASE_URL + "/api"
    : "/api",
  timeout: 10000,
  withCredentials: true,
});

/**
 * Response interceptor for the Axios instance.
 *
 * This interceptor handles:
 *
 * 1. **Successful Responses**:
 * - Automatically returns `response.data` to simplify usage of API results.
 *
 * 2. **Errors**:
 *    - Extracts key information from the error:
 *      - HTTP status (`error.response?.status`)
 *      - Request URL (`error.config?.url`)
 *      - Error message (from AxiosError, regular Error, or fallback)
 *    - In development (`import.meta.env.DEV`), logs a detailed object containing all key fields plus the full error object for easier debugging.
 *    - In production, logs a simplified object with just `status`, `url`, and `message` to avoid leaking sensitive information.
 *    - Always rejects the promise with the original error, allowing callers to handle it further.
 */
request.interceptors.response.use(
  (response) => response.data,
  (error /** @type {import('axios').AxiosError | Error | any} */) => {
    let errorMessage;

    // If it's an Axios error object
    if (error?.response?.data?.message) {
      errorMessage = error.response.data.message;
    }
    // If it's a regular Error object
    else if (error?.message) {
      errorMessage = error.message;
    }
    // For other unknown cases
    else {
      errorMessage = "No error message";
    }

    if (import.meta.env.DEV) {
      console.error("API Error:", {
        status: error.response?.status || "Unknown status",
        url: error.config?.url || "Unknown URL",
        message: errorMessage,
        fullError: error,
      });
    } else {
      console.error("API Error:", {
        status: error?.response?.status || "Unknown status",
        url: error?.config?.url || "Unknown URL",
        message: errorMessage,
      });
    }
    return Promise.reject(error);
  },
);

export default request;
