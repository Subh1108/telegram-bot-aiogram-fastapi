const API = "/api";
let TOKEN = sessionStorage.getItem("dash_token") || null;
let signupChart = null;
let activeTicketId = null;

// ---------- Auth ----------

async function login() {
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.textContent = "";
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      errEl.textContent = "Incorrect password. Try again.";
      return;
    }
    const data = await res.json();
    TOKEN = data.token;
    sessionStorage.setItem("dash_token", TOKEN);
    enterApp();
  } catch (e) {
    errEl.textContent = "Could not reach the server.";
  }
}

function logout() {
  sessionStorage.removeItem("dash_token");
  TOKEN = null;
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${TOKEN}`,
    },
  });
  if (res.status === 401) {
    logout();
    throw new Error("Session expired");
  }
  return res;
}

// ---------- Navigation ----------

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
      loadViewData(btn.dataset.view);
    });
  });
}

function loadViewData(view) {
  if (view === "overview") { loadStats(); loadActivity(); }
  if (view === "broadcast") loadBroadcastHistory();
  if (view === "tickets") loadTickets();
  if (view === "users") loadUsers();
  if (view === "settings") loadSettings();
}

// ---------- Overview ----------

async function loadStats() {
  const res = await apiFetch("/stats");
  const data = await res.json();
  document.getElementById("stat-total-users").textContent = data.total_users;
  document.getElementById("stat-active-today").textContent = data.active_today;
  document.getElementById("stat-open-tickets").textContent = data.open_tickets;
  document.getElementById("stat-broadcasts").textContent = data.broadcasts_sent;

  const labels = data.signups_last_14d.map((d) => d.date.slice(5));
  const values = data.signups_last_14d.map((d) => d.count);

  const ctx = document.getElementById("signup-chart");
  if (signupChart) signupChart.destroy();
  signupChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: "#4DD9C9",
        backgroundColor: "rgba(77,217,201,0.08)",
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#7C8B9C", font: { family: "JetBrains Mono", size: 10 } } },
        y: { grid: { color: "#232B36" }, ticks: { color: "#7C8B9C", font: { family: "JetBrains Mono", size: 10 } }, beginAtZero: true },
      },
    },
  });
}

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso + "Z")) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

async function loadActivity() {
  const res = await apiFetch("/activity");
  const events = await res.json();
  const feed = document.getElementById("activity-feed");
  feed.innerHTML = events.map((e) => `
    <div class="feed-item tag-${e.type}">
      <span class="feed-time">${timeAgo(e.created_at)}</span>
      <span><span class="tag">[${e.type}]</span> ${e.description}</span>
    </div>
  `).join("") || `<p class="hint-text">No activity yet.</p>`;
}

// ---------- Broadcast ----------

async function sendBroadcast() {
  const message = document.getElementById("broadcast-message").value.trim();
  const segment = document.getElementById("broadcast-segment").value;
  const scheduled = document.getElementById("broadcast-schedule").value;
  const resultEl = document.getElementById("broadcast-result");

  if (!message) { resultEl.textContent = "Write a message first."; return; }

  resultEl.textContent = "Sending...";
  const res = await apiFetch("/broadcast", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message, segment,
      scheduled_for: scheduled ? new Date(scheduled).toISOString() : null,
    }),
  });
  const data = await res.json();
  if (data.scheduled) {
    resultEl.textContent = "Scheduled successfully.";
  } else {
    resultEl.textContent = `Sent to ${data.sent} users (${data.failed} failed).`;
  }
  document.getElementById("broadcast-message").value = "";
  document.getElementById("broadcast-schedule").value = "";
  loadBroadcastHistory();
}

async function loadBroadcastHistory() {
  const res = await apiFetch("/broadcast/history");
  const logs = await res.json();
  document.getElementById("broadcast-history-body").innerHTML = logs.map((l) => `
    <tr>
      <td>${l.body.length > 60 ? l.body.slice(0, 60) + "…" : l.body}</td>
      <td>${l.segment}</td>
      <td>${l.sent_count}</td>
      <td>${l.failed_count}</td>
      <td>${l.sent_at ? timeAgo(l.sent_at) : (l.scheduled_for ? "scheduled" : "—")}</td>
    </tr>
  `).join("") || `<tr><td colspan="5" class="hint-text">No broadcasts yet.</td></tr>`;
}

// ---------- Tickets ----------

async function loadTickets() {
  const res = await apiFetch("/tickets");
  const tickets = await res.json();
  const list = document.getElementById("tickets-list");
  list.innerHTML = tickets.map((t) => `
    <div class="ticket-row ${t.id === activeTicketId ? "active" : ""}" onclick="openTicket(${t.id})">
      <div class="t-user">${t.user} <span class="badge badge-active">${t.status}</span></div>
      <div class="t-subject">${t.subject}</div>
    </div>
  `).join("") || `<p class="hint-text">No tickets yet.</p>`;
}

async function openTicket(id) {
  activeTicketId = id;
  loadTickets();
  const res = await apiFetch(`/tickets/${id}`);
  const t = await res.json();
  const detail = document.getElementById("ticket-detail");
  detail.innerHTML = `
    <h2>${t.user} · #${t.id}</h2>
    <div id="ticket-messages">
      ${t.messages.map((m) => `<div class="ticket-msg ${m.from_admin ? "admin" : "user"}">${m.body}</div>`).join("")}
    </div>
    <div class="ticket-reply-box">
      <textarea id="ticket-reply-text" rows="2" placeholder="Type a reply..."></textarea>
      <button class="primary-btn" onclick="sendTicketReply(${t.id})">Reply</button>
    </div>
    <button class="mini-btn" style="margin-top:10px" onclick="closeTicket(${t.id})">Mark as closed</button>
  `;
}

async function sendTicketReply(id) {
  const text = document.getElementById("ticket-reply-text").value.trim();
  if (!text) return;
  await apiFetch(`/tickets/${id}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });
  openTicket(id);
}

async function closeTicket(id) {
  await apiFetch(`/tickets/${id}/close`, { method: "POST" });
  loadTickets();
  document.getElementById("ticket-detail").innerHTML = `<p class="hint-text">Ticket closed.</p>`;
}

// ---------- Users ----------

let userSearchTimer = null;

async function loadUsers() {
  const q = document.getElementById("user-search").value.trim();
  const res = await apiFetch(`/users?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  document.getElementById("users-table-body").innerHTML = data.users.map((u) => `
    <tr>
      <td>${u.display_name} ${u.is_admin ? '<span class="badge badge-admin">admin</span>' : ""}</td>
      <td>${new Date(u.joined_at + "Z").toLocaleDateString()}</td>
      <td>${timeAgo(u.last_active_at)}</td>
      <td>${u.is_banned ? '<span class="badge badge-banned">banned</span>' : '<span class="badge badge-active">active</span>'}</td>
      <td>
        ${u.is_banned
          ? `<button class="mini-btn" onclick="unbanUser(${u.id})">Unban</button>`
          : `<button class="mini-btn danger" onclick="banUser(${u.id})">Ban</button>`}
      </td>
    </tr>
  `).join("") || `<tr><td colspan="5" class="hint-text">No users found.</td></tr>`;
}

async function banUser(id) { await apiFetch(`/users/${id}/ban`, { method: "POST" }); loadUsers(); }
async function unbanUser(id) { await apiFetch(`/users/${id}/unban`, { method: "POST" }); loadUsers(); }

// ---------- Settings ----------

async function loadSettings() {
  const res = await apiFetch("/settings");
  const data = await res.json();
  document.getElementById("maintenance-toggle").checked = data.maintenance_mode === "on";
  document.getElementById("welcome-message").value = data.welcome_message;
}

async function saveSettings() {
  const maintenance_mode = document.getElementById("maintenance-toggle").checked ? "on" : "off";
  const welcome_message = document.getElementById("welcome-message").value;
  await apiFetch("/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ maintenance_mode, welcome_message }),
  });
  document.getElementById("settings-result").textContent = "Saved.";
  setTimeout(() => (document.getElementById("settings-result").textContent = ""), 2000);
}

// ---------- Boot ----------

function enterApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  loadViewData("overview");
  setInterval(() => {
    if (document.getElementById("view-overview").classList.contains("active")) loadActivity();
  }, 8000);
}

document.getElementById("login-btn").addEventListener("click", login);
document.getElementById("login-password").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("broadcast-send-btn").addEventListener("click", sendBroadcast);
document.getElementById("save-settings-btn").addEventListener("click", saveSettings);
document.getElementById("user-search").addEventListener("input", () => {
  clearTimeout(userSearchTimer);
  userSearchTimer = setTimeout(loadUsers, 300);
});

setupNav();
if (TOKEN) enterApp();
