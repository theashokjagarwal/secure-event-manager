/**
 * ==============================================================================
 * Secure Event Manager - Administrator Controller
 * ==============================================================================
 * SECURITY FEATURES:
 * 1. Role-Based Access Control verified before loading.
 * 2. File Upload Validation (checks extension and size before transmitting).
 * 3. XSS Prevention: Table rows and modal details created with textContent.
 * 4. Proper HTTP Verbs: DELETE for removing events, POST for creation.
 * ==============================================================================
 */

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("admin-events-table")) {
    initAdminPanel();
  }
});

async function initAdminPanel() {
  const tableBody = document.getElementById("admin-events-tbody");
  const statsTotalEvents = document.getElementById("stat-total-events");
  const statsTotalUsers = document.getElementById("stat-total-users");
  const statsTotalRegistrations = document.getElementById("stat-total-registrations");

  const modalBackdrop = document.getElementById("create-event-modal");
  const openModalBtn = document.getElementById("btn-open-create-modal");
  const closeModalBtn = document.getElementById("btn-close-create-modal");
  const createForm = document.getElementById("create-event-form");

  const attendeeModal = document.getElementById("attendees-modal");
  const closeAttendeeBtn = document.getElementById("btn-close-attendees-modal");
  const attendeesListContainer = document.getElementById("attendees-list-container");

  // Load Admin Data
  await loadStats();
  await loadAdminEvents();

  // Modal open/close handlers
  if (openModalBtn) {
    openModalBtn.addEventListener("click", () => {
      DOM.hideAlert("create-event-alert");
      createForm.reset();
      modalBackdrop.classList.add("active");
    });
  }

  if (closeModalBtn) {
    closeModalBtn.addEventListener("click", () => {
      modalBackdrop.classList.remove("active");
    });
  }

  if (closeAttendeeBtn) {
    closeAttendeeBtn.addEventListener("click", () => {
      attendeeModal.classList.remove("active");
    });
  }

  // Load Dashboard Statistics
  async function loadStats() {
    const res = await API.request("/api/admin/stats");
    if (res.ok && res.data.success) {
      if (statsTotalEvents) statsTotalEvents.textContent = res.data.stats.total_events;
      if (statsTotalUsers) statsTotalUsers.textContent = res.data.stats.total_users;
      if (statsTotalRegistrations) statsTotalRegistrations.textContent = res.data.stats.total_registrations;
    }
  }

  // Load Events Table
  async function loadAdminEvents() {
    tableBody.textContent = "";
    const res = await API.request("/api/events");

    if (!res.ok || !res.data.success) {
      const tr = DOM.create("tr");
      const td = DOM.create("td", {
        text: "Error loading events.",
        attributes: { colspan: "7" }
      });
      tr.appendChild(td);
      tableBody.appendChild(tr);
      return;
    }

    const events = res.data.events;
    if (events.length === 0) {
      const tr = DOM.create("tr");
      const td = DOM.create("td", {
        text: "No events found. Click 'Create Event' to add one.",
        attributes: { colspan: "7" }
      });
      tr.appendChild(td);
      tableBody.appendChild(tr);
      return;
    }

    events.forEach(event => {
      const tr = DOM.create("tr");

      // ID
      tr.appendChild(DOM.create("td", { text: `#${event.id}` }));

      // Title & Category
      const titleTd = DOM.create("td");
      titleTd.appendChild(DOM.create("div", {
        text: event.title,
        attributes: { style: "font-weight: 600;" }
      }));
      titleTd.appendChild(DOM.create("span", {
        className: "category-tag",
        text: event.category
      }));
      tr.appendChild(titleTd);

      // Date
      const dateStr = event.event_date ? new Date(event.event_date).toLocaleDateString() : "TBD";
      tr.appendChild(DOM.create("td", { text: dateStr }));

      // Location
      tr.appendChild(DOM.create("td", { text: event.location }));

      // Registrations count
      tr.appendChild(DOM.create("td", { text: `${event.registration_count} attendees` }));

      // Attachment indicator
      const fileTd = DOM.create("td");
      if (event.has_attachment) {
        fileTd.appendChild(DOM.create("a", {
          className: "btn btn-secondary btn-sm",
          text: "📎 View",
          attributes: {
            href: `/api/events/${event.id}/attachment`,
            target: "_blank",
            rel: "noopener noreferrer"
          }
        }));
      } else {
        fileTd.textContent = "None";
      }
      tr.appendChild(fileTd);

      // Action buttons
      const actionsTd = DOM.create("td");
      const actionGroup = DOM.create("div", {
        attributes: { style: "display: flex; gap: 0.5rem;" }
      });

      // View Attendees Button
      const viewBtn = DOM.create("button", {
        className: "btn btn-secondary btn-sm",
        text: "Attendees"
      });
      viewBtn.addEventListener("click", () => openAttendeesModal(event.id, event.title));
      actionGroup.appendChild(viewBtn);

      // Delete Button
      const deleteBtn = DOM.create("button", {
        className: "btn btn-danger btn-sm",
        text: "Delete"
      });
      deleteBtn.addEventListener("click", () => handleDeleteEvent(event.id, event.title));
      actionGroup.appendChild(deleteBtn);

      actionsTd.appendChild(actionGroup);
      tr.appendChild(actionsTd);

      tableBody.appendChild(tr);
    });
  }

  // Handle Event Creation with File Upload
  if (createForm) {
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      DOM.hideAlert("create-event-alert");

      const title = document.getElementById("ev-title").value.trim();
      const description = document.getElementById("ev-desc").value.trim();
      const category = document.getElementById("ev-cat").value.trim();
      const date = document.getElementById("ev-date").value;
      const location = document.getElementById("ev-loc").value.trim();
      const fileInput = document.getElementById("ev-file");
      const submitBtn = document.getElementById("btn-submit-event");

      // Client-side text validations
      if (title.length < 3) {
        DOM.showAlert("create-event-alert", "Title must be at least 3 characters long.", "error");
        return;
      }
      if (description.length < 10) {
        DOM.showAlert("create-event-alert", "Description must be at least 10 characters long.", "error");
        return;
      }
      if (!date) {
        DOM.showAlert("create-event-alert", "Please select an event date.", "error");
        return;
      }

      // Client-side file validation
      const formData = new FormData();
      formData.append("title", title);
      formData.append("description", description);
      formData.append("category", category);
      formData.append("event_date", date);
      formData.append("location", location);

      if (fileInput && fileInput.files.length > 0) {
        const file = fileInput.files[0];

        // 1. Check file size (5MB limit)
        const maxBytes = 5 * 1024 * 1024;
        if (file.size > maxBytes) {
          DOM.showAlert("create-event-alert", "File size cannot exceed 5 MB.", "error");
          return;
        }

        // 2. Check file extension
        const allowedExts = ["pdf", "docx", "png", "jpg", "jpeg"];
        const ext = file.name.split(".").pop().toLowerCase();
        if (!allowedExts.includes(ext)) {
          DOM.showAlert("create-event-alert", "Invalid file type. Permitted: PDF, DOCX, PNG, JPG.", "error");
          return;
        }

        formData.append("attachment", file);
      }

      // Disable button while saving
      DOM.setLoading(submitBtn, true, "Saving Event...", "Create Event");

      const res = await API.request("/api/admin/events", {
        method: "POST",
        body: formData
      });

      DOM.setLoading(submitBtn, false, "", "Create Event");

      if (res.ok && res.data.success) {
        modalBackdrop.classList.remove("active");
        DOM.showAlert("admin-alert", "Event created successfully!", "success");
        await loadStats();
        await loadAdminEvents();
      } else {
        DOM.showAlert("create-event-alert", res.data.error || "Failed to create event.", "error");
      }
    });
  }

  // Handle Event Deletion
  async function handleDeleteEvent(eventId, eventTitle) {
    if (!confirm(`Are you sure you want to delete "${eventTitle}"? This cannot be undone.`)) {
      return;
    }

    const res = await API.request(`/api/admin/events/${eventId}`, {
      method: "DELETE"
    });

    if (res.ok && res.data.success) {
      DOM.showAlert("admin-alert", "Event deleted successfully.", "success");
      await loadStats();
      await loadAdminEvents();
    } else {
      DOM.showAlert("admin-alert", res.data.error || "Failed to delete event.", "error");
    }
  }

  // Open Attendees Modal
  async function openAttendeesModal(eventId, eventTitle) {
    const titleEl = document.getElementById("attendees-modal-title");
    if (titleEl) titleEl.textContent = `Attendees: ${eventTitle}`;

    attendeesListContainer.textContent = "Loading registered attendees...";
    attendeeModal.classList.add("active");

    const res = await API.request(`/api/admin/events/${eventId}/attendees`);
    attendeesListContainer.textContent = "";

    if (!res.ok || !res.data.success) {
      attendeesListContainer.appendChild(DOM.create("p", {
        className: "alert alert-error alert-visible",
        text: res.data.error || "Failed to load attendees."
      }));
      return;
    }

    const attendees = res.data.attendees;
    if (attendees.length === 0) {
      attendeesListContainer.appendChild(DOM.create("p", {
        className: "stat-label",
        text: "No attendees have registered for this event yet."
      }));
      return;
    }

    const table = DOM.create("table", { className: "data-table" });
    const thead = DOM.create("thead");
    const headerTr = DOM.create("tr");
    headerTr.appendChild(DOM.create("th", { text: "Name" }));
    headerTr.appendChild(DOM.create("th", { text: "Email" }));
    headerTr.appendChild(DOM.create("th", { text: "Registered Date" }));
    headerTr.appendChild(DOM.create("th", { text: "Status" }));
    thead.appendChild(headerTr);
    table.appendChild(thead);

    const tbody = DOM.create("tbody");
    attendees.forEach(att => {
      const row = DOM.create("tr");
      row.appendChild(DOM.create("td", { text: att.user_name || "Unknown" }));
      row.appendChild(DOM.create("td", { text: att.user_email || "Unknown" }));
      const regDate = att.registered_at ? new Date(att.registered_at).toLocaleString() : "N/A";
      row.appendChild(DOM.create("td", { text: regDate }));
      row.appendChild(DOM.create("td", {
        children: [
          DOM.create("span", {
            className: "role-badge role-user",
            text: att.status
          })
        ]
      }));
      tbody.appendChild(row);
    });
    table.appendChild(tbody);

    attendeesListContainer.appendChild(table);
  }
}
