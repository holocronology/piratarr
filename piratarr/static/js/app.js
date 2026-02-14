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

            const movies = items.filter(i => i.media_type === "movie");
            const episodes = items.filter(i => i.media_type === "episode");

            let html = "";

            // Movies section
            if (movies.length > 0 && filter !== "episode") {
                html += `<h3 class="media-section-title">Movies (${movies.length})</h3>`;
                html += `<table><thead><tr>
                    <th>Title</th><th>Subtitles</th><th>Pirate Subs</th><th>Actions</th>
                </tr></thead><tbody>`;
                for (const m of movies) {
                    html += `<tr>
                        <td>${escapeHtml(m.title)}</td>
                        <td>${m.has_subtitle ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>'}</td>
                        <td>${m.has_pirate_subtitle ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>'}</td>
                        <td>${translateButton(m)}</td>
                    </tr>`;
                }
                html += `</tbody></table>`;
            }

            // TV section — group by series then season
            if (episodes.length > 0 && filter !== "movie") {
                const seriesMap = {};
                for (const ep of episodes) {
                    const key = ep.series_title || ep.title;
                    if (!seriesMap[key]) seriesMap[key] = {};
                    const sn = ep.season_number ?? 0;
                    if (!seriesMap[key][sn]) seriesMap[key][sn] = [];
                    seriesMap[key][sn].push(ep);
                }

                const seriesNames = Object.keys(seriesMap).sort();
                html += `<h3 class="media-section-title">TV Series (${seriesNames.length} series, ${episodes.length} episodes)</h3>`;

                for (const seriesName of seriesNames) {
                    const seasons = seriesMap[seriesName];
                    const allEps = Object.values(seasons).flat();
                    const seriesHasSubs = allEps.some(e => e.has_subtitle);
                    const seriesAllPirate = allEps.every(e => e.has_pirate_subtitle || !e.has_subtitle);
                    const seriesTranslatable = allEps.filter(e => e.has_subtitle && !e.has_pirate_subtitle);
                    const seriesIds = seriesTranslatable.map(e => e.id);

                    html += `<div class="media-tree-series">
                        <div class="media-tree-header" data-toggle="series">
                            <span class="tree-expand">&#9654;</span>
                            <span class="tree-title">${escapeHtml(seriesName)}</span>
                            <span class="tree-stats">
                                ${allEps.length} eps &middot;
                                ${allEps.filter(e => e.has_pirate_subtitle).length}/${allEps.filter(e => e.has_subtitle).length} translated
                            </span>
                            ${seriesIds.length > 0
                                ? `<button class="btn btn-small btn-primary btn-translate-batch" data-media-ids='${JSON.stringify(seriesIds)}'>Translate All</button>`
                                : seriesAllPirate && seriesHasSubs ? '<span class="badge badge-success">Done</span>' : ''}
                        </div>
                        <div class="media-tree-children" style="display:none;">`;

                    const seasonNums = Object.keys(seasons).map(Number).sort((a, b) => a - b);
                    for (const sn of seasonNums) {
                        const seasonEps = seasons[sn].sort((a, b) => (a.episode_number || 0) - (b.episode_number || 0));
                        const seasonAllPirate = seasonEps.every(e => e.has_pirate_subtitle || !e.has_subtitle);
                        const seasonHasSubs = seasonEps.some(e => e.has_subtitle);
                        const seasonTranslatable = seasonEps.filter(e => e.has_subtitle && !e.has_pirate_subtitle);
                        const seasonIds = seasonTranslatable.map(e => e.id);

                        html += `<div class="media-tree-season">
                            <div class="media-tree-header media-tree-header-season" data-toggle="season">
                                <span class="tree-expand">&#9654;</span>
                                <span class="tree-title">Season ${sn}</span>
                                <span class="tree-stats">
                                    ${seasonEps.length} eps &middot;
                                    ${seasonEps.filter(e => e.has_pirate_subtitle).length}/${seasonEps.filter(e => e.has_subtitle).length} translated
                                </span>
                                ${seasonIds.length > 0
                                    ? `<button class="btn btn-small btn-primary btn-translate-batch" data-media-ids='${JSON.stringify(seasonIds)}'>Translate Season</button>`
                                    : seasonAllPirate && seasonHasSubs ? '<span class="badge badge-success">Done</span>' : ''}
                            </div>
                            <div class="media-tree-children" style="display:none;">
                                <table><thead><tr>
                                    <th>Episode</th><th>Title</th><th>Subtitles</th><th>Pirate Subs</th><th>Actions</th>
                                </tr></thead><tbody>`;

                        for (const ep of seasonEps) {
                            const epNum = ep.episode_number != null ? `E${String(ep.episode_number).padStart(2, "0")}` : "";
                            const epTitle = ep.title.replace(/^.*?-\s*/, "");
                            html += `<tr>
                                <td>${epNum}</td>
                                <td>${escapeHtml(epTitle)}</td>
                                <td>${ep.has_subtitle ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>'}</td>
                                <td>${ep.has_pirate_subtitle ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>'}</td>
                                <td>${translateButton(ep)}</td>
                            </tr>`;
                        }

                        html += `</tbody></table></div></div>`;
                    }

                    html += `</div></div>`;
                }
            }

            container.innerHTML = html;
            bindTranslateButtons(container);
            bindTreeToggles(container);
        } catch (err) {
            console.error("Failed to load media:", err);
        }
    }

    function translateButton(item) {
        if (item.has_subtitle && !item.has_pirate_subtitle) {
            return `<button class="btn btn-small btn-primary btn-translate-media" data-media-id="${item.id}">Translate</button>`;
        }
        if (item.has_pirate_subtitle) {
            return '<span class="badge badge-success">Done</span>';
        }
        return '';
    }

    function bindTranslateButtons(container) {
        // Single-item translate
        container.querySelectorAll(".btn-translate-media").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.stopPropagation();
                btn.disabled = true;
                btn.textContent = "Translating...";
                try {
                    await api(`/api/media/${btn.dataset.mediaId}/translate`, { method: "POST" });
                    await loadMedia();
                } catch (err) {
                    btn.textContent = "Failed";
                    console.error("Translation failed:", err);
                }
            });
        });

        // Batch translate (series/season)
        container.querySelectorAll(".btn-translate-batch").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const ids = JSON.parse(btn.dataset.mediaIds);
                btn.disabled = true;
                btn.textContent = `Translating ${ids.length}...`;
                try {
                    await api("/api/translate/batch", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ media_ids: ids }),
                    });
                    await loadMedia();
                } catch (err) {
                    btn.textContent = "Failed";
                    console.error("Batch translation failed:", err);
                }
            });
        });
    }

    function bindTreeToggles(container) {
        container.querySelectorAll(".media-tree-header").forEach(header => {
            header.addEventListener("click", (e) => {
                if (e.target.closest(".btn")) return;
                const children = header.nextElementSibling;
                const arrow = header.querySelector(".tree-expand");
                if (children.style.display === "none") {
                    children.style.display = "block";
                    arrow.innerHTML = "&#9660;";
                } else {
                    children.style.display = "none";
                    arrow.innerHTML = "&#9654;";
                }
            });
        });
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
    function renderPathMappings(mappings) {
        const container = document.getElementById("path-mappings-list");
        container.innerHTML = "";
        (mappings || []).forEach((mapping, idx) => {
            const row = document.createElement("div");
            row.className = "path-mapping-row";
            row.innerHTML = `
                <div class="form-group" style="display:inline-block;width:40%">
                    <label>Remote Path (Sonarr/Radarr)</label>
                    <input type="text" class="input-field mapping-remote" data-idx="${idx}" value="${escapeHtml(mapping.remote_path || "")}" placeholder="/movies">
                </div>
                <span style="display:inline-block;width:3%;text-align:center;padding-top:1.5rem;">&rarr;</span>
                <div class="form-group" style="display:inline-block;width:40%">
                    <label>Local Path (Piratarr)</label>
                    <input type="text" class="input-field mapping-local" data-idx="${idx}" value="${escapeHtml(mapping.local_path || "")}" placeholder="/data/movies">
                </div>
                <button class="btn btn-small btn-danger btn-remove-mapping" data-idx="${idx}" style="margin-left:0.5rem;margin-top:1.5rem;">Remove</button>
            `;
            container.appendChild(row);
        });

        container.querySelectorAll(".btn-remove-mapping").forEach(btn => {
            btn.addEventListener("click", () => {
                const i = parseInt(btn.dataset.idx);
                currentPathMappings.splice(i, 1);
                renderPathMappings(currentPathMappings);
            });
        });
    }

    let currentPathMappings = [];

    document.getElementById("btn-add-mapping").addEventListener("click", () => {
        currentPathMappings.push({ remote_path: "", local_path: "" });
        renderPathMappings(currentPathMappings);
    });

    async function loadSettings() {
        try {
            const settings = await api("/api/settings");
            document.getElementById("radarr-url").value = settings.radarr_url || "";
            document.getElementById("radarr-api-key").value = settings.radarr_api_key || "";
            document.getElementById("sonarr-url").value = settings.sonarr_url || "";
            document.getElementById("sonarr-api-key").value = settings.sonarr_api_key || "";
            document.getElementById("scan-interval").value = settings.scan_interval || "3600";
            document.getElementById("auto-translate").checked = settings.auto_translate === "true";
            currentPathMappings = settings.path_mappings || [];
            renderPathMappings(currentPathMappings);
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
        // Collect path mappings from the UI inputs
        const mappingRemotes = document.querySelectorAll(".mapping-remote");
        const mappingLocals = document.querySelectorAll(".mapping-local");
        const pathMappings = [];
        mappingRemotes.forEach((input, i) => {
            const remote = input.value.trim();
            const local = mappingLocals[i].value.trim();
            if (remote && local) {
                pathMappings.push({ remote_path: remote, local_path: local });
            }
        });
        currentPathMappings = pathMappings;

        const settings = {
            radarr_url: document.getElementById("radarr-url").value,
            radarr_api_key: document.getElementById("radarr-api-key").value,
            sonarr_url: document.getElementById("sonarr-url").value,
            sonarr_api_key: document.getElementById("sonarr-api-key").value,
            scan_interval: document.getElementById("scan-interval").value,
            auto_translate: document.getElementById("auto-translate").checked ? "true" : "false",
            path_mappings: pathMappings,
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
