/**
 * ==============================================================================
 * Secure Event Manager - Public Events & User Dashboard Controller
 * ==============================================================================
 * SECURITY FEATURES:
 * 1. XSS Prevention: All dynamic text (title, description, location) is rendered
 *    strictly via textContent using the DOM helper.
 * 2. Parameterized Requests: Search terms are safely passed via encodeURIComponent.
 * 3. Safe State Changes: POST for registrations, DELETE for cancellations.
 * ==============================================================================
 */

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("events-container")) {
    initPublicEvents();
  }
  if (document.getElementById("dashboard-registrations")) {
    initUserDashboard();
  }
});

/**
 * Public Events Catalog
 */
async function initPublicEvents() {
  const container = document.getElementById("events-container");
  const searchInput = document.getElementById("search-input");
  const categoryFilter = document.getElementById("category-filter");
  const searchForm = document.getElementById("search-form");

  async function loadEvents() {
    container.textContent = "";
    const loadingEl = DOM.create("div", {
      className: "stat-label",
      text: "Loading upcoming events..."
    });
    container.appendChild(loadingEl);

    const q = searchInput ? searchInput.value.trim() : "";
    const cat = categoryFilter ? categoryFilter.value : "";

    const queryParams = new URLSearchParams();
    if (q) queryParams.set("q", q);
    if (cat) queryParams.set("category", cat);

    const res = await API.request(`/api/events?${queryParams.toString()}`);
    container.textContent = "";

    if (!res.ok || !res.data.success) {
      container.appendChild(DOM.create("p", {
        className: "alert alert-error alert-visible",
        text: res.data.error || "Failed to load events. Please try again."
      }));
      return;
    }

    const events = res.data.events;
    if (events.length === 0) {
      container.appendChild(DOM.create("p", {
        className: "stat-label",
        text: "No upcoming events found matching your criteria."
      }));
      return;
    }

    events.forEach(event => {
      const card = createEventCard(event);
      container.appendChild(card);
    });
  }

  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      loadEvents();
    });
  }

  if (categoryFilter) {
    categoryFilter.addEventListener("change", loadEvents);
  }

  // Initial load
  loadEvents();
}

/**
 * Build Event Card DOM safely without innerHTML.
 */
function createEventCard(event) {
  const card = DOM.create("div", { className: "event-card" });

  // Header with Category
  const header = DOM.create("div", { className: "event-card-header" });
  const categoryTag = DOM.create("span", {
    className: "category-tag",
    text: event.category
  });
  header.appendChild(categoryTag);
  card.appendChild(header);

  // Title - SECURITY: textContent prevents XSS
  const title = DOM.create("h3", {
    className: "event-title",
    text: event.title
  });
  card.appendChild(title);

  // Description - SECURITY: textContent prevents script execution
  const desc = DOM.create("p", {
    className: "event-description",
    text: event.description
  });
  card.appendChild(desc);

  // Metadata (Date & Location)
  const meta = DOM.create("div", { className: "event-meta" });

  const formattedDate = event.event_date
    ? new Date(event.event_date).toLocaleDateString(undefined, {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      })
    : "Date TBD";

  const dateItem = DOM.create("div", {
    className: "event-meta-item",
    text: `📅 ${formattedDate}`
  });
  const locItem = DOM.create("div", {
    className: "event-meta-item",
    text: `📍 ${event.location}`
  });
  const attendeeItem = DOM.create("div", {
    className: "event-meta-item",
    text: `👥 ${event.registration_count} registered`
  });

  meta.appendChild(dateItem);
  meta.appendChild(locItem);
  meta.appendChild(attendeeItem);
  card.appendChild(meta);

  // Action Buttons
  const actions = DOM.create("div", { className: "event-card-actions" });

  // Safe file attachment download
  if (event.has_attachment) {
    const downloadBtn = DOM.create("a", {
      className: "btn btn-secondary btn-sm",
      text: "📎 View Attachment",
      attributes: {
        href: `/api/events/${event.id}/attachment`,
        target: "_blank",
        rel: "noopener noreferrer"
      }
    });
    actions.appendChild(downloadBtn);
  }

  // Register Button
  const registerBtn = DOM.create("button", {
    className: "btn btn-primary btn-sm",
    text: "Register Now"
  });

  registerBtn.addEventListener("click", async () => {
    const user = API.getUser();
    if (!user) {
      window.location.href = "/login?msg=register_required";
      return;
    }

    DOM.setLoading(registerBtn, true, "Registering...", "Register Now");

    const res = await API.request(`/api/events/${event.id}/register`, {
      method: "POST"
    });

    DOM.setLoading(registerBtn, false, "", "Register Now");

    if (res.ok && res.data.success) {
      alert(`🎉 ${res.data.message}`);
      registerBtn.textContent = "Registered ✓";
      registerBtn.disabled = true;
      registerBtn.className = "btn btn-secondary btn-sm";
    } else {
      alert(res.data.error || "Registration could not be completed.");
    }
  });

  actions.appendChild(registerBtn);
  card.appendChild(actions);

  return card;
}

/**
 * User Dashboard Controller (Manage personal registrations)
 */
async function initUserDashboard() {
  const container = document.getElementById("dashboard-registrations");
  const alertContainer = "dashboard-alert";
  const user = API.getUser();

  if (document.getElementById("user-welcome-name") && user) {
    document.getElementById("user-welcome-name").textContent = user.name;
  }

  async function loadUserRegistrations() {
    container.textContent = "";
    const res = await API.request("/api/my-registrations");

    if (!res.ok || !res.data.success) {
      DOM.showAlert(alertContainer, res.data.error || "Failed to load registrations.", "error");
      return;
    }

    const registrations = res.data.registrations;
    if (registrations.length === 0) {
      container.appendChild(DOM.create("p", {
        className: "stat-label",
        text: "You have not registered for any events yet. Explore upcoming events on the home page!"
      }));
      return;
    }

    registrations.forEach(reg => {
      const event = reg.event;
      if (!event) return;

      const card = DOM.create("div", { className: "event-card" });

      const header = DOM.create("div", { className: "event-card-header" });
      header.appendChild(DOM.create("span", {
        className: "category-tag",
        text: event.category
      }));
      header.appendChild(DOM.create("span", {
        className: "role-badge role-user",
        text: "Status: " + reg.status
      }));
      card.appendChild(header);

      card.appendChild(DOM.create("h3", {
        className: "event-title",
        text: event.title
      }));
      card.appendChild(DOM.create("p", {
        className: "event-description",
        text: event.description
      }));

      const meta = DOM.create("div", { className: "event-meta" });
      meta.appendChild(DOM.create("div", {
        className: "event-meta-item",
        text: `📅 ${new Date(event.event_date).toLocaleDateString()}`
      }));
      meta.appendChild(DOM.create("div", {
        className: "event-meta-item",
        text: `📍 ${event.location}`
      }));
      card.appendChild(meta);

      const actions = DOM.create("div", { className: "event-card-actions" });

      if (event.has_attachment) {
        actions.appendChild(DOM.create("a", {
          className: "btn btn-secondary btn-sm",
          text: "📎 Download Flyer",
          attributes: {
            href: `/api/events/${event.id}/attachment`,
            target: "_blank",
            rel: "noopener noreferrer"
          }
        }));
      }

      const cancelBtn = DOM.create("button", {
        className: "btn btn-danger btn-sm",
        text: "Cancel Registration"
      });

      cancelBtn.addEventListener("click", async () => {
        if (!confirm(`Are you sure you want to cancel your registration for "${event.title}"?`)) {
          return;
        }

        DOM.setLoading(cancelBtn, true, "Cancelling...", "Cancel Registration");
        const cancelRes = await API.request(`/api/my-registrations/${event.id}`, {
          method: "DELETE"
        });

        if (cancelRes.ok && cancelRes.data.success) {
          DOM.showAlert(alertContainer, "Registration cancelled successfully.", "success");
          loadUserRegistrations();
        } else {
          DOM.showAlert(alertContainer, cancelRes.data.error || "Failed to cancel registration.", "error");
          DOM.setLoading(cancelBtn, false, "", "Cancel Registration");
        }
      });

      actions.appendChild(cancelBtn);
      card.appendChild(actions);

      container.appendChild(card);
    });
  }

  loadUserRegistrations();
}
