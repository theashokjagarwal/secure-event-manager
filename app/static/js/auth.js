/**
 * ==============================================================================
 * Secure Event Manager - Authentication & Authorization Controller
 * ==============================================================================
 * SECURITY FEATURES:
 * 1. Dual Validation: Form validation performed both in frontend and on backend.
 * 2. Route Protection: Redirects unauthorized visitors away from dashboard and admin.
 * 3. Double-Submit Defense: Buttons disabled while async auth requests are running.
 * 4. Safe UI Rendering: Uses textContent to display user names and roles.
 * ==============================================================================
 */

document.addEventListener("DOMContentLoaded", () => {
  initNavbarAuth();
  checkRouteProtection();
  initLoginForm();
  initRegisterForm();
});

/**
 * Update top navigation bar according to current user session status.
 */
function initNavbarAuth() {
  const navContainer = document.getElementById("navbar-auth-links");
  if (!navContainer) return;

  const user = API.getUser();
  navContainer.textContent = ""; // Clear existing elements

  if (user) {
    // User profile pill
    const userPill = DOM.create("div", { className: "user-pill" });
    const nameSpan = DOM.create("span", { text: user.name });
    const roleBadge = DOM.create("span", {
      className: `role-badge ${user.role === "admin" ? "role-admin" : "role-user"}`,
      text: user.role
    });

    userPill.appendChild(nameSpan);
    userPill.appendChild(roleBadge);
    navContainer.appendChild(userPill);

    // Dashboard link
    const dashLink = DOM.create("a", {
      className: "nav-link",
      text: "My Dashboard",
      attributes: { href: "/dashboard" }
    });
    navContainer.appendChild(dashLink);

    // Admin link if user has admin role
    if (user.role === "admin") {
      const adminLink = DOM.create("a", {
        className: "nav-link",
        text: "Admin Panel",
        attributes: { href: "/admin" }
      });
      navContainer.appendChild(adminLink);
    }

    // Logout button
    const logoutBtn = DOM.create("button", {
      className: "btn btn-secondary btn-sm",
      text: "Logout"
    });
    logoutBtn.addEventListener("click", handleLogout);
    navContainer.appendChild(logoutBtn);

  } else {
    // Unauthenticated state
    const loginLink = DOM.create("a", {
      className: "nav-link",
      text: "Log In",
      attributes: { href: "/login" }
    });
    const regLink = DOM.create("a", {
      className: "btn btn-primary btn-sm",
      text: "Register",
      attributes: { href: "/register" }
    });

    navContainer.appendChild(loginLink);
    navContainer.appendChild(regLink);
  }
}

/**
 * SECURITY: Frontend route protection.
 * Prevents unauthenticated users from seeing dashboard or admin views.
 */
function checkRouteProtection() {
  const path = window.location.pathname;
  const user = API.getUser();

  // If user is already logged in, redirect them away from login/register pages
  if (user && (path === "/login" || path === "/register")) {
    window.location.href = user.role === "admin" ? "/admin" : "/dashboard";
    return;
  }

  // Dashboard requires authentication
  if (path === "/dashboard" && !user) {
    window.location.href = "/login?msg=auth_required";
    return;
  }

  // Admin panel requires admin role
  if (path === "/admin") {
    if (!user) {
      window.location.href = "/login?msg=admin_required";
      return;
    }
    if (user.role !== "admin") {
      alert("Access Denied: Administrator role is required to view this page.");
      window.location.href = "/dashboard";
      return;
    }
  }
}

/**
 * Handle Login Form Submission
 */
function initLoginForm() {
  const form = document.getElementById("login-form");
  if (!form) return;

  // Check URL query parameters for session warnings
  const params = new URLSearchParams(window.location.search);
  if (params.get("expired")) {
    DOM.showAlert("auth-alert", "Your session has expired. Please log in again.", "info");
  } else if (params.get("registered")) {
    DOM.showAlert("auth-alert", "Account created successfully! Please sign in.", "success");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    DOM.hideAlert("auth-alert");

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const submitBtn = document.getElementById("login-submit-btn");

    // Client-side quick check
    if (!email || !password) {
      DOM.showAlert("auth-alert", "Please enter both your email and password.", "error");
      return;
    }

    // Disable button to prevent double-clicks
    DOM.setLoading(submitBtn, true, "Verifying credentials...", "Sign In");

    const res = await API.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    DOM.setLoading(submitBtn, false, "", "Sign In");

    if (res.ok && res.data.success) {
      API.setToken(res.data.token);
      API.setUser(res.data.user);

      // Redirect according to user role
      if (res.data.user.role === "admin") {
        window.location.href = "/admin";
      } else {
        window.location.href = "/dashboard";
      }
    } else {
      DOM.showAlert("auth-alert", res.data.error || "Login failed.", "error");
    }
  });
}

/**
 * Handle Registration Form & Live Password Strength Feedback
 */
function initRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) return;

  const passwordInput = document.getElementById("reg-password");
  const pwdLengthEl = document.getElementById("chk-len");
  const pwdUpperEl = document.getElementById("chk-upper");
  const pwdLowerEl = document.getElementById("chk-lower");
  const pwdNumEl = document.getElementById("chk-num");
  const pwdSpecEl = document.getElementById("chk-spec");

  // Real-time password requirement checklist
  if (passwordInput && pwdLengthEl) {
    passwordInput.addEventListener("input", () => {
      const val = passwordInput.value;
      updateCheckItem(pwdLengthEl, val.length >= 8);
      updateCheckItem(pwdUpperEl, /[A-Z]/.test(val));
      updateCheckItem(pwdLowerEl, /[a-z]/.test(val));
      updateCheckItem(pwdNumEl, /[0-9]/.test(val));
      updateCheckItem(pwdSpecEl, /[!@#$%^&*(),.?":{}|<>\-_]/.test(val));
    });
  }

  function updateCheckItem(element, isValid) {
    if (isValid) {
      element.classList.add("valid");
      element.textContent = "✓ " + element.dataset.label;
    } else {
      element.classList.remove("valid");
      element.textContent = "○ " + element.dataset.label;
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    DOM.hideAlert("auth-alert");

    const name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = passwordInput.value;
    const confirmPassword = document.getElementById("reg-confirm-password").value;
    const submitBtn = document.getElementById("register-submit-btn");

    // Client-side validations
    if (name.length < 2) {
      DOM.showAlert("auth-alert", "Please provide your full name (at least 2 characters).", "error");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      DOM.showAlert("auth-alert", "Please enter a valid email address.", "error");
      return;
    }

    if (password !== confirmPassword) {
      DOM.showAlert("auth-alert", "Passwords do not match.", "error");
      return;
    }

    if (password.length < 8) {
      DOM.showAlert("auth-alert", "Password must be at least 8 characters long.", "error");
      return;
    }

    // Disable submit button while request is sent
    DOM.setLoading(submitBtn, true, "Creating Account...", "Create Account");

    const res = await API.request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password })
    });

    DOM.setLoading(submitBtn, false, "", "Create Account");

    if (res.ok && res.data.success) {
      window.location.href = "/login?registered=1";
    } else {
      DOM.showAlert("auth-alert", res.data.error || "Registration failed.", "error");
    }
  });
}

/**
 * Safe Logout Handler
 */
async function handleLogout() {
  try {
    await API.request("/api/auth/logout", { method: "POST" });
  } catch (err) {
    console.error("Logout error", err);
  } finally {
    API.clearSession();
    window.location.href = "/login";
  }
}
