/**
 * ==============================================================================
 * Secure Event Manager - Public Events, Multi-City Filter & AI Prep Guide
 * ==============================================================================
 * SECURITY FEATURES:
 * 1. Safe text rendering via DOM.create (no innerHTML).
 * 2. Strict external link safety (rel="noopener noreferrer").
 * 3. Parameterized search queries.
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
 * Public Events Catalog with City & College Filters
 */
async function initPublicEvents() {
  const container = document.getElementById("events-container");
  const countBadge = document.getElementById("events-count-badge");
  const searchInput = document.getElementById("search-input");
  const cityFilter = document.getElementById("city-filter");
  const eventTypeFilter = document.getElementById("event-type-filter");
  const categoryFilter = document.getElementById("category-filter");
  const searchForm = document.getElementById("search-form");

  const aiModal = document.getElementById("ai-guide-modal");
  const closeAiModalBtn = document.getElementById("btn-close-ai-guide");

  if (closeAiModalBtn && aiModal) {
    closeAiModalBtn.addEventListener("click", () => {
      aiModal.classList.remove("active");
    });
  }

  async function loadEvents() {
    container.textContent = "";
    if (countBadge) countBadge.textContent = "Searching...";

    const q = searchInput ? searchInput.value.trim() : "";
    const city = cityFilter ? cityFilter.value : "";
    const eventType = eventTypeFilter ? eventTypeFilter.value : "";
    const cat = categoryFilter ? categoryFilter.value : "";

    const queryParams = new URLSearchParams();
    if (q) queryParams.set("q", q);
    if (city) queryParams.set("city", city);
    if (eventType) queryParams.set("event_type", eventType);
    if (cat) queryParams.set("category", cat);

    const res = await API.request(`/api/events?${queryParams.toString()}`);
    container.textContent = "";

    if (!res.ok || !res.data.success) {
      if (countBadge) countBadge.textContent = "Error loading";
      container.appendChild(DOM.create("p", {
        className: "alert alert-error alert-visible",
        text: res.data.error || "Failed to load events. Please try again."
      }));
      return;
    }

    const events = res.data.events;
    if (countBadge) countBadge.textContent = `${events.length} Events Available`;

    if (events.length === 0) {
      container.appendChild(DOM.create("div", {
        className: "stat-card",
        attributes: { style: "grid-column: 1 / -1; text-align: center; padding: 2.5rem;" },
        children: [
          DOM.create("h3", { text: "No Events Found Matching Your Filter" }),
          DOM.create("p", {
            className: "form-hint",
            text: "Try selecting 'All Cities' or 'All Event Types', or search for colleges like IIT, BITS, or IIIT."
          })
        ]
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

  if (cityFilter) cityFilter.addEventListener("change", loadEvents);
  if (eventTypeFilter) eventTypeFilter.addEventListener("change", loadEvents);
  if (categoryFilter) categoryFilter.addEventListener("change", loadEvents);

  // Initial load
  loadEvents();
}

/**
 * Build Event Card DOM safely without innerHTML.
 */
function createEventCard(event) {
  const card = DOM.create("div", { className: "event-card" });

  // Top Badge Row: Category, Event Type, City, AI badge
  const header = DOM.create("div", {
    className: "event-card-header",
    attributes: { style: "display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;" }
  });

  header.appendChild(DOM.create("span", {
    className: "category-tag",
    text: event.category
  }));

  header.appendChild(DOM.create("span", {
    className: "role-badge role-user",
    text: event.event_type || "Tech Fest"
  }));

  header.appendChild(DOM.create("span", {
    className: "role-badge",
    attributes: { style: "background-color: #fef3c7; color: #b45309;" },
    text: `📍 ${event.city}`
  }));

  if (event.is_ai_discovered) {
    header.appendChild(DOM.create("span", {
      className: "role-badge",
      attributes: { style: "background-color: #e0e7ff; color: #4338ca;" },
      text: "🤖 AI Sourced"
    }));
  }

  card.appendChild(header);

  // College or Host Institution Banner
  if (event.college_name) {
    const hostEl = DOM.create("div", {
      attributes: { style: "font-size: 0.82rem; font-weight: 700; color: #2563eb; margin: 0.4rem 0 0.2rem 0;" },
      text: `🏛️ ${event.college_name}`
    });
    card.appendChild(hostEl);
  }

  // Title - SECURITY: textContent prevents XSS
  const title = DOM.create("h3", {
    className: "event-title",
    text: event.title
  });
  card.appendChild(title);

  // Description
  const desc = DOM.create("p", {
    className: "event-description",
    text: event.description
  });
  card.appendChild(desc);

  // Metadata (Date, Location, Attendees)
  const meta = DOM.create("div", { className: "event-meta" });

  const formattedDate = event.event_date
    ? new Date(event.event_date).toLocaleDateString(undefined, {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric"
      })
    : "Date TBD";

  meta.appendChild(DOM.create("div", {
    className: "event-meta-item",
    text: `📅 ${formattedDate}`
  }));

  meta.appendChild(DOM.create("div", {
    className: "event-meta-item",
    text: `📍 ${event.location}`
  }));

  meta.appendChild(DOM.create("div", {
    className: "event-meta-item",
    text: `👥 ${event.registration_count} registered on EventSecure`
  }));

  card.appendChild(meta);

  // Action Buttons Group
  const actions = DOM.create("div", {
    className: "event-card-actions",
    attributes: { style: "flex-wrap: wrap; gap: 0.5rem;" }
  });

  // 1. Direct Official Application Link
  if (event.application_link) {
    const applyBtn = DOM.create("a", {
      className: "btn btn-primary btn-sm",
      text: "🔗 Apply Official",
      attributes: {
        href: event.application_link,
        target: "_blank",
        rel: "noopener noreferrer"
      }
    });
    actions.appendChild(applyBtn);
  }

  // 2. AI Prep Guide Button
  const aiGuideBtn = DOM.create("button", {
    className: "btn btn-secondary btn-sm",
    text: "🤖 AI Roadmap"
  });
  aiGuideBtn.addEventListener("click", () => openAiGuideModal(event.id));
  actions.appendChild(aiGuideBtn);

  // 3. View Flyer / Attachment if present
  if (event.has_attachment) {
    const downloadBtn = DOM.create("a", {
      className: "btn btn-secondary btn-sm",
      text: "📎 Flyer",
      attributes: {
        href: `/api/events/${event.id}/attachment`,
        target: "_blank",
        rel: "noopener noreferrer"
      }
    });
    actions.appendChild(downloadBtn);
  }

  // 4. RSVP on EventSecure
  const rsvpBtn = DOM.create("button", {
    className: "btn btn-secondary btn-sm",
    text: "RSVP Here"
  });

  rsvpBtn.addEventListener("click", async () => {
    const user = API.getUser();
    if (!user) {
      window.location.href = "/login?msg=register_required";
      return;
    }

    DOM.setLoading(rsvpBtn, true, "Saving...", "RSVP Here");

    const res = await API.request(`/api/events/${event.id}/register`, {
      method: "POST"
    });

    DOM.setLoading(rsvpBtn, false, "", "RSVP Here");

    if (res.ok && res.data.success) {
      alert(`🎉 ${res.data.message}`);
      rsvpBtn.textContent = "Attending ✓";
      rsvpBtn.disabled = true;
    } else {
      alert(res.data.error || "RSVP could not be completed.");
    }
  });

  actions.appendChild(rsvpBtn);
  card.appendChild(actions);

  return card;
}

/**
 * AI Event Roadmap Modal Popup
 */
async function openAiGuideModal(eventId) {
  const modal = document.getElementById("ai-guide-modal");
  const titleEl = document.getElementById("ai-guide-title");
  const bodyEl = document.getElementById("ai-guide-body");
  const applyBtn = document.getElementById("ai-guide-apply-btn");

  if (!modal || !bodyEl) return;

  bodyEl.textContent = "🤖 Generating intelligent preparation roadmap...";
  modal.classList.add("active");

  const res = await API.request(`/api/events/${eventId}/ai-guide`);
  bodyEl.textContent = "";

  if (!res.ok || !res.data.success) {
    bodyEl.appendChild(DOM.create("p", {
      className: "alert alert-error alert-visible",
      text: "Failed to generate AI roadmap."
    }));
    return;
  }

  const guide = res.data.ai_guide;
  if (titleEl) titleEl.textContent = `🤖 AI Prep Guide: ${guide.event_title}`;

  // Host and City Info
  bodyEl.appendChild(DOM.create("div", {
    attributes: { style: "background: #f1f5f9; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 1rem;" },
    children: [
      DOM.create("div", { text: `📍 Location: ${guide.city}` }),
      DOM.create("div", { text: `🏛️ Host: ${guide.college_or_host}` })
    ]
  }));

  // Recommended Tech Skills
  bodyEl.appendChild(DOM.create("h4", {
    attributes: { style: "font-weight: 700; margin-bottom: 0.4rem;" },
    text: "🛠️ Key Tech Stack & Skills to Master:"
  }));

  const skillsList = DOM.create("ul", {
    attributes: { style: "margin-left: 1.5rem; margin-bottom: 1rem; color: #334155;" }
  });
  guide.recommended_skills.forEach(skill => {
    skillsList.appendChild(DOM.create("li", { text: skill }));
  });
  bodyEl.appendChild(skillsList);

  // Recommended Team Strategy
  bodyEl.appendChild(DOM.create("h4", {
    attributes: { style: "font-weight: 700; margin-bottom: 0.4rem;" },
    text: "👥 Recommended Team Composition:"
  }));
  bodyEl.appendChild(DOM.create("p", {
    attributes: { style: "color: #334155; margin-bottom: 1rem;" },
    text: guide.team_strategy
  }));

  // AI Tactical Tip
  bodyEl.appendChild(DOM.create("div", {
    attributes: { style: "background: #eff6ff; border-left: 4px solid #3b82f6; padding: 0.75rem 1rem; border-radius: 4px;" },
    children: [
      DOM.create("strong", { text: "💡 AI Winning Tip: " }),
      DOM.create("span", { text: guide.ai_tip })
    ]
  }));

  // Link application button
  if (applyBtn) {
    applyBtn.href = guide.application_url;
  }
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
        text: `📍 ${event.city}`
      }));
      card.appendChild(header);

      if (event.college_name) {
        card.appendChild(DOM.create("div", {
          attributes: { style: "font-size: 0.8rem; font-weight: 700; color: #2563eb;" },
          text: `🏛️ ${event.college_name}`
        }));
      }

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

      if (event.application_link) {
        actions.appendChild(DOM.create("a", {
          className: "btn btn-primary btn-sm",
          text: "🔗 Apply Official",
          attributes: {
            href: event.application_link,
            target: "_blank",
            rel: "noopener noreferrer"
          }
        }));
      }

      const cancelBtn = DOM.create("button", {
        className: "btn btn-danger btn-sm",
        text: "Cancel RSVP"
      });

      cancelBtn.addEventListener("click", async () => {
        if (!confirm(`Are you sure you want to cancel your RSVP for "${event.title}"?`)) {
          return;
        }

        DOM.setLoading(cancelBtn, true, "Cancelling...", "Cancel RSVP");
        const cancelRes = await API.request(`/api/my-registrations/${event.id}`, {
          method: "DELETE"
        });

        if (cancelRes.ok && cancelRes.data.success) {
          DOM.showAlert(alertContainer, "Registration cancelled successfully.", "success");
          loadUserRegistrations();
        } else {
          DOM.showAlert(alertContainer, cancelRes.data.error || "Failed to cancel registration.", "error");
          DOM.setLoading(cancelBtn, false, "", "Cancel RSVP");
        }
      });

      actions.appendChild(cancelBtn);
      card.appendChild(actions);

      container.appendChild(card);
    });
  }

  loadUserRegistrations();
}
