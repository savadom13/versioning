(function () {
    "use strict";

    const API = "/api";

    function toast(message, type) {
        const el = document.getElementById("toast");
        el.classList.remove("hidden");
        const div = document.createElement("div");
        div.className = type === "error" ? "bg-red-100 text-red-800 p-3 rounded shadow" : "bg-green-100 text-green-800 p-3 rounded shadow";
        div.textContent = message;
        el.appendChild(div);
        setTimeout(function () {
            div.remove();
            if (el.children.length === 0) el.classList.add("hidden");
        }, 4000);
    }

    function apiGet(path) {
        return fetch(API + path, { credentials: "same-origin" }).then(function (r) {
            const j = r.json().catch(function () { return null; });
            if (!r.ok) return j.then(function (body) { throw { status: r.status, body: body }; });
            return j;
        });
    }

    function apiPost(path, body) {
        return fetch(API + path, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }).then(function (r) {
            const j = r.json().catch(function () { return null; });
            if (!r.ok) return j.then(function (body) { throw { status: r.status, body: body }; });
            return j;
        });
    }

    function apiPatch(path, body) {
        return fetch(API + path, {
            method: "PATCH",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }).then(function (r) {
            const j = r.json().catch(function () { return null; });
            if (!r.ok) return j.then(function (body) { throw { status: r.status, body: body }; });
            return j;
        });
    }

    function apiDelete(path, body) {
        return fetch(API + path, {
            method: "DELETE",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
        }).then(function (r) {
            if (r.status === 204) return {};
            const j = r.json().catch(function () { return null; });
            if (!r.ok) return j.then(function (body) { throw { status: r.status, body: body }; });
            return j;
        });
    }

    function getRoute() {
        const hash = window.location.hash.slice(1) || "/";
        const parts = hash.split("/").filter(Boolean);
        if (parts[0] === "versions" && parts.length >= 3) {
            return { screen: "versions", entityType: parts[1], entityId: parseInt(parts[2], 10) };
        }
        if (parts[0] === "trash") return { screen: "trash" };
        return { screen: "main" };
    }

    function showScreen(name) {
        document.getElementById("screen-main").classList.add("hidden");
        document.getElementById("screen-trash").classList.add("hidden");
        document.getElementById("screen-versions").classList.add("hidden");
        const el = document.getElementById("screen-" + name);
        if (el) el.classList.remove("hidden");
    }

    function renderMain() {
        showScreen("main");
        Promise.all([apiGet("/signals"), apiGet("/assets")]).then(function (results) {
            const signals = results[0];
            const assets = results[1];
            renderSignalsList(signals);
            renderAssetsList(assets, signals);
            renderNewAssetSignalsPicker(signals);
        }).catch(function (err) {
            toast((err.body && err.body.error) || "Failed to load", "error");
        });
    }

    function renderSignalsList(signals) {
        const list = document.getElementById("signals-list");
        list.innerHTML = signals.map(function (s) {
            return (
                '<div class="bg-white p-4 rounded shadow" data-signal-id="' + s.id + '">' +
                '<div class="flex justify-between mb-2">' +
                '<div><p class="font-semibold">f=' + escapeHtml(s.frequency) + ', mod=' + escapeHtml(s.modulation) + ', p=' + escapeHtml(s.power) + '</p>' +
                '<p class="text-sm text-gray-500">Created by ' + escapeHtml(s.created_by) + ' | Updated by ' + escapeHtml(s.updated_by) + '</p></div>' +
                '<a href="#/versions/signals/' + s.id + '" class="text-blue-600">Versions</a></div>' +
                '<div class="flex gap-2 items-center flex-wrap">' +
                '<input type="number" step="any" class="signal-freq border p-1 w-24" value="' + s.frequency + '">' +
                '<input type="text" class="signal-mod border p-1 w-24" value="' + escapeAttr(s.modulation) + '">' +
                '<input type="number" step="any" class="signal-pow border p-1 w-24" value="' + s.power + '">' +
                '<button type="button" class="btn-signal-update bg-green-600 text-white px-3 py-1 rounded">Update</button>' +
                '<button type="button" class="btn-signal-delete bg-red-600 text-white px-3 py-1 rounded">Delete</button>' +
                '</div><input type="hidden" class="signal-lock" value="' + s.lock_version + '">' +
                '</div>'
            );
        }).join("");

        list.querySelectorAll(".btn-signal-update").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const card = btn.closest("[data-signal-id]");
                const id = card.getAttribute("data-signal-id");
                const freq = card.querySelector(".signal-freq").value;
                const mod = card.querySelector(".signal-mod").value;
                const pow = card.querySelector(".signal-pow").value;
                const lock = card.querySelector(".signal-lock").value;
                apiPatch("/signals/" + id, { frequency: parseFloat(freq), modulation: mod, power: parseFloat(pow), lock_version: parseInt(lock, 10) })
                    .then(function (updated) {
                        card.querySelector(".signal-lock").value = updated.lock_version;
                        toast("Signal #" + id + " updated.", "success");
                    })
                    .catch(function (err) {
                        toast((err.body && err.body.error) || "Update failed", "error");
                        if (err.status === 409) renderMain();
                    });
            });
        });

        list.querySelectorAll(".btn-signal-delete").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const card = btn.closest("[data-signal-id]");
                const id = card.getAttribute("data-signal-id");
                const lock = card.querySelector(".signal-lock").value;
                if (!confirm("Delete signal #" + id + "?")) return;
                apiDelete("/signals/" + id, { lock_version: parseInt(lock, 10) })
                    .then(function () {
                        toast("Signal #" + id + " deleted.", "success");
                        renderMain();
                    })
                    .catch(function (err) {
                        toast((err.body && err.body.error) || "Delete failed", "error");
                        if (err.status === 409) renderMain();
                    });
            });
        });
    }

    function renderNewAssetSignalsPicker(signals) {
        const container = document.getElementById("new-asset-signals-list");
        container.innerHTML = signals.map(function (s) {
            return '<label class="signals-option block p-1 rounded hover:bg-gray-100"><input type="checkbox" name="signal_ids" value="' + s.id + '" class="mr-2">#' + s.id + ' | f=' + s.frequency + ' | ' + escapeHtml(s.modulation) + ' | p=' + s.power + '</label>';
        }).join("");
        setupSearchableSignals(container.closest(".searchable-signals"));
    }

    function renderAssetsList(assets, signals) {
        const list = document.getElementById("assets-list");
        list.innerHTML = assets.map(function (a) {
            const signalIds = a.signal_ids || [];
            return (
                '<div class="bg-white p-4 rounded shadow" data-asset-id="' + a.id + '">' +
                '<div class="flex justify-between mb-2">' +
                '<div><p class="font-semibold">' + escapeHtml(a.name) + '</p><p class="text-sm">' + escapeHtml(a.description) + '</p>' +
                '<p class="text-sm text-gray-500">Signals: ' + (signalIds.length ? signalIds.join(", ") : "none") + '</p>' +
                '<p class="text-sm text-gray-500">Created by ' + escapeHtml(a.created_by) + ' | Updated by ' + escapeHtml(a.updated_by) + '</p></div>' +
                '<a href="#/versions/assets/' + a.id + '" class="text-blue-600">Versions</a></div>' +
                '<div class="mb-2"><input type="text" class="asset-name border p-1 mr-2 mb-2" value="' + escapeAttr(a.name) + '" placeholder="Name">' +
                '<input type="text" class="asset-desc border p-1 mb-2 w-full" value="' + escapeAttr(a.description) + '" placeholder="Description"></div>' +
                '<div class="searchable-signals relative mb-2"><button type="button" class="signals-toggle border p-2 w-full text-left bg-white rounded">Select signals</button>' +
                '<div class="signals-panel hidden absolute z-10 mt-1 w-full bg-white border rounded shadow p-2">' +
                '<input type="text" class="signals-search border p-2 w-full mb-2" placeholder="Search">' +
                '<div class="signals-list max-h-48 overflow-y-auto space-y-1 asset-signals-list" data-signal-ids="' + escapeAttr(signalIds.join(",")) + '"></div></div></div>' +
                '<button type="button" class="btn-asset-update bg-green-600 text-white px-3 py-1 rounded">Update</button> ' +
                '<button type="button" class="btn-asset-delete bg-red-600 text-white px-3 py-1 rounded">Delete</button>' +
                '<input type="hidden" class="asset-lock" value="' + a.lock_version + '">' +
                '</div>'
            );
        }).join("");

        list.querySelectorAll("[data-asset-id]").forEach(function (card) {
            const assetId = card.getAttribute("data-asset-id");
            const signalsListEl = card.querySelector(".asset-signals-list");
            const initialIds = (signalsListEl.getAttribute("data-signal-ids") || "").split(",").filter(Boolean).map(Number);
            signalsListEl.removeAttribute("data-signal-ids");
            signals.forEach(function (s) {
                const label = document.createElement("label");
                label.className = "signals-option block p-1 rounded hover:bg-gray-100";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.name = "signal_ids";
                cb.value = String(s.id);
                if (initialIds.indexOf(s.id) >= 0) cb.checked = true;
                label.appendChild(cb);
                label.appendChild(document.createTextNode(" #" + s.id + " | f=" + s.frequency + " | " + s.modulation + " | p=" + s.power));
                signalsListEl.appendChild(label);
            });
            setupSearchableSignals(card.querySelector(".searchable-signals"));

            card.querySelector(".btn-asset-update").addEventListener("click", function () {
                const name = card.querySelector(".asset-name").value;
                const description = card.querySelector(".asset-desc").value;
                const checked = card.querySelectorAll(".asset-signals-list input:checked");
                const signal_ids = Array.from(checked).map(function (c) { return parseInt(c.value, 10); });
                const lock = parseInt(card.querySelector(".asset-lock").value, 10);
                apiPatch("/assets/" + assetId, { name: name, description: description, signal_ids: signal_ids, lock_version: lock })
                    .then(function (updated) {
                        card.querySelector(".asset-lock").value = updated.lock_version;
                        toast("Asset #" + assetId + " updated.", "success");
                    })
                    .catch(function (err) {
                        toast((err.body && err.body.error) || "Update failed", "error");
                        if (err.status === 409) renderMain();
                    });
            });

            card.querySelector(".btn-asset-delete").addEventListener("click", function () {
                const lock = parseInt(card.querySelector(".asset-lock").value, 10);
                if (!confirm("Delete asset #" + assetId + "?")) return;
                apiDelete("/assets/" + assetId, { lock_version: lock })
                    .then(function () {
                        toast("Asset #" + assetId + " deleted.", "success");
                        renderMain();
                    })
                    .catch(function (err) {
                        toast((err.body && err.body.error) || "Delete failed", "error");
                        if (err.status === 409) renderMain();
                    });
            });
        });
    }

    function updateSignalsToggleText(wrapper) {
        var toggle = wrapper.querySelector(".signals-toggle");
        var checked = wrapper.querySelectorAll("input[type=checkbox]:checked");
        if (checked.length === 0) toggle.textContent = "Select signals";
        else toggle.textContent = checked.length + " selected";
    }

    function setupSearchableSignals(wrapper) {
        if (!wrapper || wrapper.dataset.setup) return;
        wrapper.dataset.setup = "1";
        var toggle = wrapper.querySelector(".signals-toggle");
        var panel = wrapper.querySelector(".signals-panel");
        var search = wrapper.querySelector(".signals-search");
        var options = wrapper.querySelectorAll(".signals-option");
        toggle.addEventListener("click", function () {
            panel.classList.toggle("hidden");
            if (!panel.classList.contains("hidden")) search.focus();
        });
        search.addEventListener("input", function () {
            var q = search.value.trim().toLowerCase();
            options.forEach(function (opt) {
                opt.classList.toggle("hidden", q && !opt.textContent.toLowerCase().includes(q));
            });
        });
        wrapper.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
            cb.addEventListener("change", function () { updateSignalsToggleText(wrapper); });
        });
        document.addEventListener("click", function (e) {
            if (!wrapper.contains(e.target)) panel.classList.add("hidden");
        });
        updateSignalsToggleText(wrapper);
    }

    function renderTrash() {
        showScreen("trash");
        apiGet("/trash").then(function (items) {
            const list = document.getElementById("trash-list");
            if (!items.length) {
                list.innerHTML = '<div class="bg-white p-4 rounded shadow text-gray-600">Trash is empty</div>';
                return;
            }
            list.innerHTML = items.map(function (item) {
                return (
                    '<div class="bg-white p-4 rounded shadow">' +
                    '<p class="font-semibold">' + escapeHtml(item.entity_type) + ' #' + item.id + '</p>' +
                    '<p class="text-sm">Name: ' + escapeHtml(item.name || "n/a") + '</p>' +
                    '<p class="text-sm text-gray-500">Deleted by ' + escapeHtml(item.deleted_by || "") + ' at ' + (item.deleted_at || "") + '</p>' +
                    '</div>'
                );
            }).join("");
        }).catch(function (err) {
            toast((err.body && err.body.error) || "Failed to load trash", "error");
        });
    }

    function renderVersions(entityType, entityId) {
        showScreen("versions");
        document.getElementById("versions-title").textContent = "Versions for " + entityType + " #" + entityId;
        document.getElementById("versions-back").href = "#/";
        apiGet("/versions/" + entityType + "/" + entityId).then(function (versions) {
            const list = document.getElementById("versions-list");
            list.innerHTML = versions.map(function (v) {
                return (
                    '<div class="bg-white p-4 rounded shadow">' +
                    '<p class="font-semibold">Version ' + v.version + ' (' + escapeHtml(v.operation) + ')</p>' +
                    '<p class="text-sm text-gray-500">Changed by ' + escapeHtml(v.changed_by || "") + '</p>' +
                    '<pre class="bg-gray-100 p-2 mt-2 text-sm overflow-auto">' + escapeHtml(JSON.stringify(v.snapshot, null, 2)) + '</pre>' +
                    '<p class="text-xs text-gray-400 mt-2">Hash: ' + escapeHtml(v.hash) + '</p></div>'
                );
            }).join("");
        }).catch(function (err) {
            toast((err.body && err.body.error) || "Failed to load versions", "error");
        });
    }

    function escapeHtml(s) {
        if (s == null) return "";
        var div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    function escapeAttr(s) {
        if (s == null) return "";
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function route() {
        const r = getRoute();
        if (r.screen === "main") renderMain();
        else if (r.screen === "trash") renderTrash();
        else if (r.screen === "versions" && r.entityType && r.entityId) renderVersions(r.entityType, r.entityId);
        else renderMain();
    }

    window.addEventListener("hashchange", route);
    window.addEventListener("load", function () {
        apiGet("/session").then(function (data) {
            document.getElementById("active-user-input").value = data.active_user || "";
        }).catch(function () {});
        document.getElementById("active-user-btn").addEventListener("click", function () {
            var user = document.getElementById("active-user-input").value.trim() || "system";
            apiPost("/session", { active_user: user }).then(function () {
                toast("Active user set.", "success");
            }).catch(function (err) {
                toast((err.body && err.body.error) || "Failed", "error");
            });
        });
        document.getElementById("btn-create-signal").addEventListener("click", function () {
            var freq = document.getElementById("new-signal-frequency").value;
            var mod = document.getElementById("new-signal-modulation").value;
            var pow = document.getElementById("new-signal-power").value;
            apiPost("/signals", { frequency: parseFloat(freq) || 0, modulation: mod || "", power: parseFloat(pow) || 0 })
                .then(function () {
                    document.getElementById("new-signal-frequency").value = "";
                    document.getElementById("new-signal-modulation").value = "";
                    document.getElementById("new-signal-power").value = "";
                    toast("Signal created.", "success");
                    renderMain();
                })
                .catch(function (err) {
                    toast((err.body && err.body.error) || "Create failed", "error");
                });
        });
        document.getElementById("btn-create-asset").addEventListener("click", function () {
            var name = document.getElementById("new-asset-name").value;
            var desc = document.getElementById("new-asset-description").value;
            var checked = document.querySelectorAll("#new-asset-signals-list input:checked");
            var signal_ids = Array.from(checked).map(function (c) { return parseInt(c.value, 10); });
            apiPost("/assets", { name: name || "", description: desc || "", signal_ids: signal_ids })
                .then(function () {
                    document.getElementById("new-asset-name").value = "";
                    document.getElementById("new-asset-description").value = "";
                    document.querySelectorAll("#new-asset-signals-list input:checked").forEach(function (c) { c.checked = false; });
                    toast("Asset created.", "success");
                    renderMain();
                })
                .catch(function (err) {
                    toast((err.body && err.body.error) || "Create failed", "error");
                });
        });
        route();
    });
})();
