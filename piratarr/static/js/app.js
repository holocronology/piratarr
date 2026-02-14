/* Piratarr - Frontend application logic */

document.addEventListener("DOMContentLoaded", () => {
    // Navigation
    const navLinks = document.querySelectorAll(".nav-link");
    const pages = document.querySelectorAll(".page");

    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const page = link.dataset.page;

            navLinks.forEach(l => l.classList.remove("active"));
            link.classList.add("active");

            pages.forEach(p => p.classList.remove("active"));
            document.getElementById(`page-${page}`).classList.add("active");

            // Load data for the page
            if (page === "dashboard") loadDashboard();
            if (page === "media") loadMedia();
            if (page === "jobs") loadJobs();
            if (page === "settings") loadSettings();
        });
    });

    // Initial load
    loadDashboard();

    // --- Dashboard ---
    async function loadDashboard() {
        try {
            const status = await api("/api/status");
            document.getElementById("stat-total-media").textContent = status.media.total;
            document.getElementById("stat-with-subs").textContent = status.media.with_subtitles;
            document.getElementById("stat-pirate-subs").textContent = status.media.with_pirate_subtitles;
            document.getElementById("stat-pending").textContent = status.jobs.pending;

            const scannerStatus = document.getElementById("scanner-status");
            if (status.is_scanning) {
                scannerStatus.textContent = "Scanning...";
                scannerStatus.className = "badge badge-warning";
            } else if (status.scanner_running) {
                scannerStatus.textContent = "Running";
                scannerStatus.className = "badge badge-success";
            } else {
                scannerStatus.textContent = "Stopped";
                scannerStatus.className = "badge badge-danger";
            }

            document.getElementById("last-scan").textContent =
                status.last_scan ? new Date(status.last_scan).toLocaleString() : "Never";

            // Load recent jobs
            const jobs = await api("/api/jobs");
            const recentEl = document.getElementById("recent-jobs");
            if (jobs.length === 0) {
                recentEl.innerHTML = '<p class="muted">No translation jobs yet.</p>';
            } else {
                recentEl.innerHTML = jobs.slice(0, 10).map(job => `
                    <div class="job-item">
                        <span class="job-title">${escapeHtml(job.media_title)}</span>
                        <span class="${statusBadgeClass(job.status)}">${job.status}</span>
                        <div class="job-time">${job.created_at ? new Date(job.created_at).toLocaleString() : ""}</div>
                    </div>
                `).join("");
            }
        } catch (err) {
            console.error("Failed to load dashboard:", err);
        }
    }

    // Scan Now button
    document.getElementById("btn-scan-now").addEventListener("click", async () => {
        const btn = document.getElementById("btn-scan-now");
        btn.disabled = true;
        btn.textContent = "Scanning...";
        try {
            await api("/api/scan", { method: "POST" });
            await loadDashboard();
        } catch (err) {
            console.error("Scan failed:", err);
        } finally {
            btn.disabled = false;
            btn.textContent = "Scan Now";
        }
    });

    // --- Media Library ---
    async function loadMedia() {
        const filter = document.getElementById("media-type-filter").value;
        const params = filter ? `?type=${filter}` : "";
        try {
            const items = await api(`/api/media${params}`);
            const container = document.getElementById("media-list");
            if (items.length === 0) {
                container.innerHTML = '<p class="muted">No media found. Configure Sonarr/Radarr in Settings and run a scan.</p>';
                return;
            }
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>Type</th>
                            <th>Subtitles</th>
                            <th>Pirate Subs</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map(item => `
                            <tr>
                                <td>${escapeHtml(item.title)}</td>
                                <td>${item.media_type}</td>
                                <td>${item.has_subtitle
                                    ? '<span class="badge badge-success">Yes</span>'
                                    : '<span class="badge badge-danger">No</span>'}</td>
                                <td>${item.has_pirate_subtitle
                                    ? '<span class="badge badge-success">Yes</span>'
                                    : '<span class="badge badge-danger">No</span>'}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        } catch (err) {
            console.error("Failed to load media:", err);
        }
    }

    document.getElementById("media-type-filter").addEventListener("change", loadMedia);
    document.getElementById("btn-refresh-media").addEventListener("click", loadMedia);

    // --- Translation Jobs ---
    async function loadJobs() {
        const filter = document.getElementById("job-status-filter").value;
        const params = filter ? `?status=${filter}` : "";
        try {
            const jobs = await api(`/api/jobs${params}`);
            const container = document.getElementById("jobs-list");
            if (jobs.length === 0) {
                container.innerHTML = '<p class="muted">No translation jobs found.</p>';
                return;
            }
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Media</th>
                            <th>Status</th>
                            <th>Subtitles</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${jobs.map(job => `
                            <tr>
                                <td>${job.id}</td>
                                <td>${escapeHtml(job.media_title)}</td>
                                <td><span class="${statusBadgeClass(job.status)}">${job.status}</span></td>
                                <td>${job.subtitle_count || "-"}</td>
                                <td>${job.created_at ? new Date(job.created_at).toLocaleString() : "-"}</td>
                                <td>
                                    ${job.status === "failed" ? `<button class="btn btn-small btn-secondary btn-retry" data-job-id="${job.id}">Retry</button>` : ""}
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;

            // Retry buttons
            container.querySelectorAll(".btn-retry").forEach(btn => {
                btn.addEventListener("click", async () => {
                    await api(`/api/jobs/${btn.dataset.jobId}/retry`, { method: "POST" });
                    loadJobs();
                });
            });
        } catch (err) {
            console.error("Failed to load jobs:", err);
        }
    }

    document.getElementById("job-status-filter").addEventListener("change", loadJobs);
    document.getElementById("btn-refresh-jobs").addEventListener("click", loadJobs);

    // --- Translate Preview ---
    document.getElementById("btn-translate").addEventListener("click", async () => {
        const text = document.getElementById("translate-input").value;
        if (!text.trim()) return;
        try {
            const result = await api("/api/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            const output = document.getElementById("translate-output");
            output.textContent = result.translated;
            output.classList.add("visible");
        } catch (err) {
            console.error("Translation failed:", err);
        }
    });

    document.getElementById("btn-translate-file").addEventListener("click", async () => {
        const path = document.getElementById("srt-path-input").value;
        if (!path.trim()) return;
        const output = document.getElementById("translate-file-output");
        try {
            const result = await api("/api/translate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path })
            });
            output.textContent = result.message
                ? `${result.message}\nOutput: ${result.job.output_path}\nSubtitles: ${result.job.subtitle_count} entries`
                : JSON.stringify(result, null, 2);
            output.classList.add("visible");
        } catch (err) {
            output.textContent = `Error: ${err.message}`;
            output.classList.add("visible");
        }
    });

    // --- Settings ---
    async function loadSettings() {
        try {
            const settings = await api("/api/settings");
            document.getElementById("radarr-url").value = settings.radarr_url || "";
            document.getElementById("radarr-api-key").value = settings.radarr_api_key || "";
            document.getElementById("sonarr-url").value = settings.sonarr_url || "";
            document.getElementById("sonarr-api-key").value = settings.sonarr_api_key || "";
            document.getElementById("scan-interval").value = settings.scan_interval || "3600";
            document.getElementById("auto-translate").checked = (settings.auto_translate || "true") === "true";
        } catch (err) {
            console.error("Failed to load settings:", err);
        }
    }

    // Test connection buttons
    document.querySelectorAll(".btn-test").forEach(btn => {
        btn.addEventListener("click", async () => {
            const service = btn.dataset.service;
            const url = document.getElementById(`${service}-url`).value;
            const apiKey = document.getElementById(`${service}-api-key`).value;
            const resultEl = document.getElementById(`${service}-test-result`);

            if (!url || !apiKey) {
                resultEl.textContent = "Please enter URL and API key";
                resultEl.style.color = "var(--warning)";
                return;
            }

            resultEl.textContent = "Testing...";
            resultEl.style.color = "var(--text-secondary)";

            try {
                const result = await api("/api/settings/test", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ service, url, api_key: apiKey })
                });

                if (result.success) {
                    resultEl.textContent = "Connection successful!";
                    resultEl.style.color = "var(--success)";
                } else {
                    resultEl.textContent = `Connection failed: ${result.error || "Unknown error"}`;
                    resultEl.style.color = "var(--danger)";
                }
            } catch (err) {
                resultEl.textContent = `Error: ${err.message}`;
                resultEl.style.color = "var(--danger)";
            }
        });
    });

    // Save settings
    document.getElementById("btn-save-settings").addEventListener("click", async () => {
        const settings = {
            radarr_url: document.getElementById("radarr-url").value,
            radarr_api_key: document.getElementById("radarr-api-key").value,
            sonarr_url: document.getElementById("sonarr-url").value,
            sonarr_api_key: document.getElementById("sonarr-api-key").value,
            scan_interval: document.getElementById("scan-interval").value,
            auto_translate: document.getElementById("auto-translate").checked ? "true" : "false",
        };

        const resultEl = document.getElementById("settings-save-result");
        try {
            await api("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(settings)
            });
            resultEl.textContent = "Settings saved!";
            resultEl.style.color = "var(--success)";
        } catch (err) {
            resultEl.textContent = `Error: ${err.message}`;
            resultEl.style.color = "var(--danger)";
        }
    });

    // --- Helpers ---
    async function api(url, options = {}) {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.error || `HTTP ${resp.status}`);
        }
        return resp.json();
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function statusBadgeClass(status) {
        const map = {
            pending: "badge badge-warning",
            processing: "badge badge-info",
            completed: "badge badge-success",
            failed: "badge badge-danger",
        };
        return map[status] || "badge";
    }
});
