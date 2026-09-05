import { createServer } from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";
import { URL } from "node:url";
import { joinSession, createCanvas } from "@github/copilot-sdk/extension";

const SLEEPER_URL = "https://api.sleeper.app/v1/players/nfl";
const SLEEPER_TRENDING_URL = "https://api.sleeper.app/v1/players/nfl/trending";
const TRENDING_LOOKBACK_HOURS = 24;
const TRENDING_LIMIT = 25;
const TRENDING_CONTEXT_TOP_N = 10;
const servers = new Map();
let session;

function stateRoot() {
    // Extensions run with the repository session as their working directory.
    // Keep provider state beside the checked-out code, not in session artifacts.
    return path.join(process.cwd(), "state");
}

function trendingRawRoot() {
    return path.join(stateRoot(), "players", "trending", "raw");
}

async function listSnapshots() {
    const rawRoot = path.join(stateRoot(), "players", "raw");
    try {
        const names = (await fs.readdir(rawRoot))
            .filter((name) => /^sleeper-players-\d{4}-\d{2}-\d{2}T\d{6}(?:\d{3})?Z\.json$/.test(name))
            .sort()
            .reverse();
        return names.map((name) => path.join(rawRoot, name));
    } catch (error) {
        if (error.code === "ENOENT") return [];
        throw error;
    }
}

async function readSnapshot(snapshotPath) {
    const payload = JSON.parse(await fs.readFile(snapshotPath, "utf8"));
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("Sleeper snapshot must be a JSON object keyed by player id");
    }
    return payload;
}

function normalizePlayers(payload) {
    return Object.entries(payload)
        .filter(([, record]) => record && typeof record === "object" && !Array.isArray(record))
        .map(([providerId, record]) => ({
            provider_id: String(record.player_id || providerId),
            full_name: String(record.full_name || ""),
            position: record.position ?? null,
            fantasy_positions: Array.isArray(record.fantasy_positions)
                ? [...new Set(record.fantasy_positions.map((value) => String(value).toUpperCase()))].sort()
                : [],
            team: record.team ?? null,
            status: record.status ?? null,
            active: Boolean(record.active),
            injury_status: record.injury_status ?? null,
            search_rank: record.search_rank ?? null,
            espn_id: record.espn_id ?? null,
        }));
}

function filterPlayers(players, { name, position, team, activeOnly, limit = 20 } = {}) {
    const nameFilter = name ? String(name).toLowerCase() : null;
    const positionFilter = position ? String(position).toUpperCase() : null;
    const teamFilter = team ? String(team).toUpperCase() : null;
    return players
        .filter((player) => {
            if (nameFilter && !player.full_name.toLowerCase().includes(nameFilter)) return false;
            if (positionFilter && !player.fantasy_positions.includes(positionFilter)) return false;
            if (teamFilter && String(player.team || "").toUpperCase() !== teamFilter) return false;
            if (activeOnly && !player.active) return false;
            return true;
        })
        .slice(0, Math.max(0, Number(limit) || 0));
}

async function stateInfo() {
    const snapshots = await listSnapshots();
    if (!snapshots.length) {
        return { exists: false, provider: "sleeper", state_root: stateRoot() };
    }
    const snapshot = snapshots[0];
    const stat = await fs.stat(snapshot);
    const payload = await readSnapshot(snapshot);
    return {
        exists: true,
        provider: "sleeper",
        snapshot,
        retrieved_at: stat.mtime.toISOString(),
        record_count: Object.keys(payload).length,
        state_root: stateRoot(),
    };
}

async function ensureState({ refresh = false } = {}) {
    const current = await stateInfo();
    if (current.exists && !refresh) return { ...current, fetched: false };

    const response = await fetch(SLEEPER_URL, {
        headers: { accept: "application/json", "user-agent": "nflcompanion/0.1" },
    });
    if (!response.ok) throw new Error(`Sleeper API returned HTTP ${response.status}`);
    const payload = await response.json();
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("Sleeper API response must be a JSON object");
    }

    const retrievedAt = new Date();
    const iso = retrievedAt.toISOString();
    const stamp = `${iso.slice(0, 10)}T${iso.slice(11, 13)}${iso.slice(14, 16)}${iso.slice(17, 19)}${iso.slice(20, 23)}Z`;
    const rawRoot = path.join(stateRoot(), "players", "raw");
    const rawPath = path.join(rawRoot, `sleeper-players-${stamp}.json`);
    const manifestPath = path.join(stateRoot(), "players", `sleeper-players-${stamp}.md`);
    await fs.mkdir(rawRoot, { recursive: true });
    const temporaryPath = `${rawPath}.${process.pid}.tmp`;
    await fs.writeFile(temporaryPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    await fs.rename(temporaryPath, rawPath);
    const manifest = [
        "---",
        "provider: sleeper",
        `retrieved_at: ${retrievedAt.toISOString()}`,
        `endpoint: ${SLEEPER_URL}`,
        `record_count: ${Object.keys(payload).length}`,
        `raw_snapshot: ${path.relative(stateRoot(), rawPath).replaceAll(path.sep, "/")}`,
        "---",
        "",
        "# Sleeper player snapshot",
        "",
        "Immutable read-only provider snapshot. Later fetches create new files.",
        "",
    ].join("\n");
    await fs.writeFile(manifestPath, manifest, "utf8");
    return { ...(await stateInfo()), fetched: true };
}

async function queryState({ refresh = false, ...filters } = {}) {
    const current = await ensureState({ refresh });
    const players = normalizePlayers(await readSnapshot(current.snapshot));
    const matches = filterPlayers(players, filters);
    return { ...current, count: matches.length, players: matches };
}

async function listTrendingSnapshots() {
    try {
        const names = (await fs.readdir(trendingRawRoot()))
            .filter((name) => /^sleeper-trending-\d{4}-\d{2}-\d{2}T\d{6}(?:\d{3})?Z\.json$/.test(name))
            .sort()
            .reverse();
        return names.map((name) => path.join(trendingRawRoot(), name));
    } catch (error) {
        if (error.code === "ENOENT") return [];
        throw error;
    }
}

async function readTrendingSnapshot(snapshotPath) {
    const payload = JSON.parse(await fs.readFile(snapshotPath, "utf8"));
    if (!payload || !Array.isArray(payload.add) || !Array.isArray(payload.drop)) {
        throw new Error("Trending snapshot must include 'add' and 'drop' arrays");
    }
    return payload;
}

async function trendingStateInfo() {
    const snapshots = await listTrendingSnapshots();
    if (!snapshots.length) {
        return { exists: false, provider: "sleeper", state_root: stateRoot() };
    }
    const snapshot = snapshots[0];
    const stat = await fs.stat(snapshot);
    const payload = await readTrendingSnapshot(snapshot);
    return {
        exists: true,
        provider: "sleeper",
        snapshot,
        retrieved_at: stat.mtime.toISOString(),
        add_count: payload.add.length,
        drop_count: payload.drop.length,
        state_root: stateRoot(),
    };
}

async function fetchTrendingDirection(direction, { lookbackHours = TRENDING_LOOKBACK_HOURS, limit = TRENDING_LIMIT } = {}) {
    const url = `${SLEEPER_TRENDING_URL}/${direction}?lookback_hours=${lookbackHours}&limit=${limit}`;
    const response = await fetch(url, {
        headers: { accept: "application/json", "user-agent": "nflcompanion/0.1" },
    });
    if (!response.ok) throw new Error(`Sleeper trending API returned HTTP ${response.status} for ${direction}`);
    const payload = await response.json();
    if (!Array.isArray(payload)) throw new Error(`Sleeper trending API response for ${direction} must be a JSON array`);
    return payload;
}

// Trending activity changes constantly, so every call writes a new dated
// snapshot rather than reusing the previous one, unless a very recent
// snapshot already exists (avoids duplicate fetches from rapid reloads).
async function ensureTrendingState({ refresh = false, maxAgeMinutes = 15, lookbackHours = TRENDING_LOOKBACK_HOURS, limit = TRENDING_LIMIT } = {}) {
    const current = await trendingStateInfo();
    if (current.exists && !refresh) {
        const ageMinutes = (Date.now() - new Date(current.retrieved_at).getTime()) / 60000;
        if (ageMinutes < maxAgeMinutes) return { ...current, fetched: false };
    }

    const [addEntries, dropEntries] = await Promise.all([
        fetchTrendingDirection("add", { lookbackHours, limit }),
        fetchTrendingDirection("drop", { lookbackHours, limit }),
    ]);

    const retrievedAt = new Date();
    const iso = retrievedAt.toISOString();
    const stamp = `${iso.slice(0, 10)}T${iso.slice(11, 13)}${iso.slice(14, 16)}${iso.slice(17, 19)}${iso.slice(20, 23)}Z`;
    const rawRoot = trendingRawRoot();
    const rawPath = path.join(rawRoot, `sleeper-trending-${stamp}.json`);
    const manifestPath = path.join(stateRoot(), "players", "trending", `sleeper-trending-${stamp}.md`);
    await fs.mkdir(rawRoot, { recursive: true });
    const payload = {
        provider: "sleeper",
        retrieved_at: retrievedAt.toISOString(),
        lookback_hours: lookbackHours,
        limit,
        add: addEntries,
        drop: dropEntries,
    };
    const temporaryPath = `${rawPath}.${process.pid}.tmp`;
    await fs.writeFile(temporaryPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    await fs.rename(temporaryPath, rawPath);
    const manifest = [
        "---",
        "provider: sleeper",
        `retrieved_at: ${retrievedAt.toISOString()}`,
        `lookback_hours: ${lookbackHours}`,
        `limit: ${limit}`,
        `add_count: ${addEntries.length}`,
        `drop_count: ${dropEntries.length}`,
        `raw_snapshot: ${path.relative(stateRoot(), rawPath).replaceAll(path.sep, "/")}`,
        "---",
        "",
        "# Sleeper trending player snapshot",
        "",
        "Immutable read-only provider snapshot of add/drop trending activity. A new",
        "snapshot is written on every fetch instead of overwriting the previous one.",
        "",
    ].join("\n");
    await fs.writeFile(manifestPath, manifest, "utf8");
    return { ...(await trendingStateInfo()), fetched: true };
}

function enrichTrending(entries, nameIndex) {
    return entries.map((entry) => {
        const player = nameIndex.get(String(entry.player_id)) || {};
        return {
            provider_id: String(entry.player_id),
            count: entry.count ?? null,
            full_name: player.full_name || null,
            position: player.position ?? null,
            fantasy_positions: player.fantasy_positions || [],
            team: player.team ?? null,
        };
    });
}

async function buildPlayerNameIndex() {
    const index = new Map();
    const snapshots = await listSnapshots();
    if (!snapshots.length) return index;
    for (const player of normalizePlayers(await readSnapshot(snapshots[0]))) {
        index.set(player.provider_id, player);
    }
    return index;
}

function filterTrending(entries, { position, team, limit = TRENDING_LIMIT } = {}) {
    const positionFilter = position ? String(position).toUpperCase() : null;
    const teamFilter = team ? String(team).toUpperCase() : null;
    return entries
        .filter((entry) => {
            if (positionFilter && !entry.fantasy_positions.includes(positionFilter)) return false;
            if (teamFilter && String(entry.team || "").toUpperCase() !== teamFilter) return false;
            return true;
        })
        .slice(0, Math.max(0, Number(limit) || 0));
}

async function queryTrendingState({ refresh = false, direction = "add", position, team, limit = TRENDING_LIMIT } = {}) {
    if (direction !== "add" && direction !== "drop") {
        throw new Error("direction must be 'add' or 'drop'");
    }
    const current = await ensureTrendingState({ refresh });
    const payload = await readTrendingSnapshot(current.snapshot);
    const nameIndex = await buildPlayerNameIndex();
    const enriched = enrichTrending(payload[direction], nameIndex);
    const matches = filterTrending(enriched, { position, team, limit });
    return { ...current, direction, count: matches.length, players: matches };
}

function summarizeTrendingForContext(payload, nameIndex) {
    const describe = (entry) => {
        const player = nameIndex.get(String(entry.player_id));
        const label = player?.full_name
            ? `${player.full_name} (${player.fantasy_positions?.join("/") || player.position || "?"}${player.team ? `, ${player.team}` : ""})`
            : `player_id ${entry.player_id}`;
        return `${label} - ${entry.count}`;
    };
    const topAdds = payload.add.slice(0, TRENDING_CONTEXT_TOP_N).map(describe);
    const topDrops = payload.drop.slice(0, TRENDING_CONTEXT_TOP_N).map(describe);
    return [
        `Sleeper trending players (last ${payload.lookback_hours}h, retrieved ${payload.retrieved_at}):`,
        `Top adds: ${topAdds.join("; ") || "none"}`,
        `Top drops: ${topDrops.join("; ") || "none"}`,
        "Use the sleeper_query_trending_players tool for full/filtered lists.",
    ].join("\n");
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[character]));
}

function renderHtml() {
    return `<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Sleeper player data</title>
<style>
body { margin: 0; padding: 1.5rem; background: var(--background-color-default,#fff);
 color: var(--text-color-default,#1f2328); font-family: var(--font-sans,system-ui,sans-serif); }
input,select,button { font: inherit; padding: .45rem; margin: .2rem; }
button { cursor: pointer; } .meta { color: var(--text-color-muted,#656d76); }
table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
th,td { border-bottom: 1px solid var(--border-color-default,#d0d7de); padding: .45rem; text-align: left; }
</style></head><body>
<h1>Sleeper player data</h1>
<p class="meta" id="status">Loading local state...</p>
<form id="filters"><input name="name" placeholder="Name">
<input name="position" placeholder="Position" size="8"><input name="team" placeholder="Team" size="8">
<label><input type="checkbox" name="activeOnly"> active only</label>
<input name="limit" type="number" min="1" value="20" size="4"><button>Query</button>
<button type="button" id="refresh">Fetch latest</button></form>
<table><thead><tr><th>Name</th><th>Position</th><th>Team</th><th>Status</th><th>Active</th></tr></thead>
<tbody id="players"></tbody></table>
<script>
const form = document.querySelector("#filters"), status = document.querySelector("#status");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function query(refresh = false) {
  const params = new URLSearchParams(new FormData(form)); if (refresh) params.set("refresh","1");
  status.textContent = refresh ? "Fetching Sleeper data..." : "Reading local state...";
  const response = await fetch("/api/query?" + params); const data = await response.json();
  if (!response.ok) { status.textContent = data.error || "Query failed"; return; }
  status.textContent = data.record_count + " players; snapshot updated " + data.retrieved_at +
    (data.fetched ? " (fetched now)" : " (local)");
  document.querySelector("#players").innerHTML = data.players.map(p =>
    "<tr><td>"+esc(p.full_name)+"</td><td>"+esc(p.fantasy_positions.join(", "))+
    "</td><td>"+esc(p.team)+"</td><td>"+esc(p.status)+"</td><td>"+(p.active?"yes":"no")+"</td></tr>").join("");
}
form.addEventListener("submit", e => { e.preventDefault(); query(); });
document.querySelector("#refresh").addEventListener("click", () => query(true)); query();
</script></body></html>`;
}

async function startServer() {
    const server = createServer(async (request, response) => {
        try {
            const requestUrl = new URL(request.url, "http://127.0.0.1");
            if (requestUrl.pathname === "/api/query") {
                const data = await queryState({
                    name: requestUrl.searchParams.get("name") || undefined,
                    position: requestUrl.searchParams.get("position") || undefined,
                    team: requestUrl.searchParams.get("team") || undefined,
                    activeOnly: requestUrl.searchParams.get("activeOnly") === "on",
                    limit: requestUrl.searchParams.get("limit") || 20,
                    refresh: requestUrl.searchParams.get("refresh") === "1",
                });
                response.setHeader("Content-Type", "application/json; charset=utf-8");
                response.end(JSON.stringify(data));
                return;
            }
            response.setHeader("Content-Type", "text/html; charset=utf-8");
            response.end(renderHtml());
        } catch (error) {
            response.statusCode = 500;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify({ error: error.message }));
        }
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const address = server.address();
    return { server, url: `http://127.0.0.1:${address.port}/` };
}

session = await joinSession({
    hooks: {
        onSessionStart: async () => {
            try {
                const state = await ensureTrendingState({ refresh: true });
                const payload = await readTrendingSnapshot(state.snapshot);
                const nameIndex = await buildPlayerNameIndex();
                await session.log(
                    `Fetched Sleeper trending players (${payload.add.length} adds, ${payload.drop.length} drops) into ${state.snapshot}`,
                    { ephemeral: true }
                );
                return { additionalContext: summarizeTrendingForContext(payload, nameIndex) };
            } catch (error) {
                await session.log(`Could not refresh Sleeper trending players: ${error.message}`, { level: "warning", ephemeral: true });
                try {
                    const cached = await trendingStateInfo();
                    if (cached.exists) {
                        const payload = await readTrendingSnapshot(cached.snapshot);
                        const nameIndex = await buildPlayerNameIndex();
                        return {
                            additionalContext:
                                `${summarizeTrendingForContext(payload, nameIndex)}\n` +
                                "(Could not refresh; showing the last cached snapshot.)",
                        };
                    }
                } catch {
                    // Fall through and start the session without trending context.
                }
                return undefined;
            }
        },
    },
    tools: [
        {
            name: "sleeper_ensure_player_state",
            description: "Check for local Sleeper player state and fetch it from the public API only when absent, or refresh when requested.",
            parameters: {
                type: "object",
                properties: { refresh: { type: "boolean", description: "Fetch a new snapshot even when local state exists." } },
            },
            handler: async (args) => JSON.stringify(await ensureState(args)),
        },
        {
            name: "sleeper_query_players",
            description: "Query the local Sleeper NFL player snapshot by name, position, team, and active status.",
            parameters: {
                type: "object",
                properties: {
                    name: { type: "string" }, position: { type: "string" }, team: { type: "string" },
                    activeOnly: { type: "boolean" }, limit: { type: "integer", minimum: 0 },
                },
            },
            handler: async (args) => JSON.stringify(await queryState(args)),
        },
        {
            name: "sleeper_query_trending_players",
            description: "Query the local Sleeper trending add/drop player snapshot captured at session start (or refresh it).",
            parameters: {
                type: "object",
                properties: {
                    direction: { type: "string", enum: ["add", "drop"], description: "Whether to list trending adds or drops. Defaults to 'add'." },
                    position: { type: "string" }, team: { type: "string" },
                    limit: { type: "integer", minimum: 0 },
                    refresh: { type: "boolean", description: "Fetch a new trending snapshot even when a recent one exists." },
                },
            },
            handler: async (args) => JSON.stringify(await queryTrendingState(args)),
        },
    ],
    canvases: [
        createCanvas({
            id: "sleeper-player-data",
            displayName: "Sleeper player data",
            description: "Query the local Sleeper NFL player snapshot and inspect its update time.",
            actions: [
                {
                    name: "query_players",
                    description: "Query local player state using optional filters.",
                    inputSchema: { type: "object", properties: { name: { type: "string" }, position: { type: "string" }, team: { type: "string" }, activeOnly: { type: "boolean" }, limit: { type: "integer" } } },
                    handler: async (ctx) => queryState(ctx.input),
                },
                {
                    name: "refresh_state",
                    description: "Fetch and store a new Sleeper player snapshot.",
                    handler: async () => ensureState({ refresh: true }),
                },
                {
                    name: "query_trending",
                    description: "Query local trending add/drop state using optional filters.",
                    inputSchema: { type: "object", properties: { direction: { type: "string", enum: ["add", "drop"] }, position: { type: "string" }, team: { type: "string" }, limit: { type: "integer" } } },
                    handler: async (ctx) => queryTrendingState(ctx.input),
                },
            ],
            open: async (ctx) => {
                let entry = servers.get(ctx.instanceId);
                if (!entry) {
                    entry = await startServer();
                    servers.set(ctx.instanceId, entry);
                }
                return { title: "Sleeper player data", url: entry.url };
            },
            onClose: async (ctx) => {
                const entry = servers.get(ctx.instanceId);
                if (entry) {
                    servers.delete(ctx.instanceId);
                    await new Promise((resolve) => entry.server.close(() => resolve()));
                }
            },
        }),
    ],
});
