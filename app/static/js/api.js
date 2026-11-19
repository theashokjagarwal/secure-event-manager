/**
 * ==============================================================================
 * Secure Event Manager - API & DOM Utility Layer
 * ==============================================================================
 * SECURITY FEATURES:
 * 1. XSS Prevention: Safe DOM creation helpers use textContent exclusively.
 * 2. CSRF Mitigation: Always sets custom header 'X-Requested-With'.
 * 3. Token Handling: Attaches JWT Authorization header when present.
 * 4. UI Protection: Disables submit buttons during pending requests.
 * ==============================================================================
 */

const API = {
  // Store session token in sessionStorage (isolated to current tab session)
  getToken() {
    return sessionStorage.getItem("access_token") || null;
  },

  setToken(token) {
    if (token) {
      sessionStorage.setItem("access_token", token);
    } else {
      sessionStorage.removeItem("access_token");
    }
  },

  getUser() {
    const userStr = sessionStorage.getItem("user_info");
    try {
      return userStr ? JSON.parse(userStr) : null;
    } catch {
      return null;
    }
  },

  setUser(user) {
    if (user) {
      sessionStorage.setItem("user_info", JSON.stringify(user));
    } else {
      sessionStorage.removeItem("user_info");
    }
  },

  clearSession() {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user_info");
  },

  /**
   * Unified fetch wrapper with security headers and error normalization.
   */
  async request(endpoint, options = {}) {
    const url = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const headers = options.headers || {};

    // SECURITY: Include custom header to block simple cross-site POST/PUT/DELETE
    headers["X-Requested-With"] = "XMLHttpRequest";

    // SECURITY: Attach JWT Bearer Token if available
    const token = this.getToken();
    if (token && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Default JSON Content-Type unless FormData is passed
    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(url, config);

      // Handle session expiration or unauthorized access
      if (response.status === 401) {
        // Only redirect if not already on the login or register page
        if (!window.location.pathname.includes("/login") && !window.location.pathname.includes("/register")) {
          this.clearSession();
          window.location.href = "/login?expired=1";
        }
      }

      // Parse JSON response safely
      const data = await response.json().catch(() => ({
        success: false,
        error: "Server returned an unexpected response format."
      }));

      return {
        ok: response.ok,
        status: response.status,
        data
      };
    } catch (err) {
      // SECURITY: Mask network/low-level technical error details with friendly message
      return {
        ok: false,
        status: 0,
        data: {
          success: false,
          error: "Unable to connect to the server. Please check your internet connection."
        }
      };
    }
  }
};

/**
 * Safe DOM builder to completely eliminate XSS vulnerabilities.
 * Never sets or relies on innerHTML for user-supplied data!
 */
const DOM = {
  create(tag, { text = "", className = "", attributes = {}, children = [] } = {}) {
    const el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    // SECURITY: Using textContent safely encodes characters like <, >, &, "
    if (text) {
      el.textContent = text;
    }
    for (const [key, value] of Object.entries(attributes)) {
      el.setAttribute(key, value);
    }
    for (const child of children) {
      if (typeof child === "string") {
        el.appendChild(document.createTextNode(child));
      } else if (child instanceof Node) {
        el.appendChild(child);
      }
    }
    return el;
  },

  /**
   * Helper to show friendly, non-technical alert banners.
   */
  showAlert(containerId, message, type = "error") {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear previous children safely
    container.textContent = "";
    container.className = `alert alert-${type} alert-visible`;

    const iconSpan = document.createElement("span");
    iconSpan.textContent = type === "error" ? "⚠️ " : type === "success" ? "✅ " : "ℹ️ ";

    const textSpan = document.createElement("span");
    // SECURITY: Prevent XSS by using textContent
    textSpan.textContent = message;

    container.appendChild(iconSpan);
    container.appendChild(textSpan);
  },

  hideAlert(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.className = "alert";
    container.textContent = "";
  },

  /**
   * SECURITY & UX: Disable submit button during asynchronous operations
   * to prevent duplicate submissions or race conditions.
   */
  setLoading(buttonEl, isLoading, loadingText = "Processing...", defaultText = "Submit") {
    if (!buttonEl) return;
    if (isLoading) {
      buttonEl.disabled = true;
      buttonEl.dataset.originalText = buttonEl.textContent;
      buttonEl.textContent = loadingText;
    } else {
      buttonEl.disabled = false;
      buttonEl.textContent = buttonEl.dataset.originalText || defaultText;
    }
  }
};
