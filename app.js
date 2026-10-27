(() => {
  "use strict";

  const rawConfig = window.CHAT_ANIMATIONS_CONFIG || {};
  const params = new URLSearchParams(window.location.search || "");

  const stage = document.getElementById("stage");
  const fallbackEl = document.getElementById("fallback");
  const setupPanel = document.getElementById("setup-panel");
  const statusEl = document.getElementById("connection-status");
  const logEl = document.getElementById("log");
  const channelForm = document.getElementById("channel-form");
  const channelInput = document.getElementById("channel-input");
  const scaleInput = document.getElementById("scale-input");
  const durationInput = document.getElementById("duration-input");
  const fitInput = document.getElementById("fit-input");
  const alignInput = document.getElementById("align-input");
  const commandsOnlyInput = document.getElementById("commands-only-input");
  const obsUrlInput = document.getElementById("obs-url");
  const copyUrlButton = document.getElementById("copy-url");
  const testChatForm = document.getElementById("test-chat-form");
  const testUserInput = document.getElementById("test-user");
  const testTextInput = document.getElementById("test-text");
  const animationListEl = document.getElementById("animation-list");

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function paramBool(name, fallback = false) {
    if (!params.has(name)) return fallback;
    const value = String(params.get(name) || "").trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(value)) return true;
    if (["0", "false", "no", "off"].includes(value)) return false;
    return fallback;
  }

  function paramNumber(names, fallback) {
    for (const name of Array.isArray(names) ? names : [names]) {
      if (!params.has(name)) continue;
      const value = Number(params.get(name));
      if (Number.isFinite(value)) return value;
    }
    return fallback;
  }

  function normalizeChannel(value) {
    return String(value || "")
      .trim()
      .replace(/^https?:\/\/(?:www\.)?twitch\.tv\//i, "")
      .replace(/^@/, "")
      .split(/[/?#\s]/)[0]
      .toLowerCase();
  }

  function parseChannels(value) {
    return [...new Set(String(value || "").split(",").map(normalizeChannel).filter(Boolean))];
  }

  const ignoredFromParams = String(params.get("ignore") || "")
    .split(",")
    .map(s => s.trim().toLowerCase())
    .filter(Boolean);

  const settings = {
    assetFolder: String(rawConfig.assetFolder || "asset").replace(/^\/+|\/+$/g, ""),
    defaultDurationMs: clamp(paramNumber(["durationMs", "duration"], Number(rawConfig.defaultDurationMs) || 5000), 300, 120000),
    autoDuration: paramBool("autoDuration", rawConfig.autoDuration !== false),
    globalCooldownMs: clamp(paramNumber(["cooldownMs", "globalCooldownMs"], Number(rawConfig.globalCooldownMs) || 2000), 0, 120000),
    sameAnimationCooldownMs: clamp(paramNumber(["sameCooldownMs", "sameAnimationCooldownMs"], Number(rawConfig.sameAnimationCooldownMs) || 15000), 0, 3600000),
    perUserCooldownMs: clamp(paramNumber(["userCooldownMs", "perUserCooldownMs"], Number(rawConfig.perUserCooldownMs) || 10000), 0, 3600000),
    maxQueue: Math.round(clamp(paramNumber(["queueMax", "maxQueue"], Number(rawConfig.maxQueue) || 3), 0, 20)),
    commandsOnly: paramBool("commandsOnly", Boolean(rawConfig.commandsOnly)),
    scalePercent: clamp(paramNumber("scale", Number(rawConfig.scalePercent) || 100), 10, 100),
    fit: String(params.get("fit") || rawConfig.fit || "contain").toLowerCase() === "cover" ? "cover" : "contain",
    align: ["center", "bottom", "top", "left", "right"].includes(String(params.get("align") || rawConfig.align || "center").toLowerCase())
      ? String(params.get("align") || rawConfig.align || "center").toLowerCase()
      : "center",
    ignoredUsers: new Set([
      ...(Array.isArray(rawConfig.ignoredUsers) ? rawConfig.ignoredUsers : []),
      ...ignoredFromParams
    ].map(s => String(s).trim().toLowerCase()).filter(Boolean))
  };

  let channels = parseChannels(params.get("channel") || params.get("twitch") || rawConfig.defaultChannel || "");
  const setupRequested = paramBool("setup") || paramBool("debug");
  let showSetup = setupRequested || channels.length === 0;

  function applyVisualSettings() {
    document.documentElement.style.setProperty("--scale", String(settings.scalePercent / 100));
    document.documentElement.style.setProperty("--fit", settings.fit);
    if (stage) stage.dataset.align = settings.align;
    if (setupPanel) setupPanel.hidden = !showSetup;
    document.body?.classList?.toggle("setup", showSetup);
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
    console.info(`[Twitch Chat Animations] ${text}`);
  }

  function log(text) {
    console.info(`[Twitch Chat Animations] ${text}`);
    if (!logEl || !showSetup) return;
    const item = document.createElement("li");
    item.textContent = text;
    logEl.prepend(item);
    while (logEl.children.length > 30) logEl.lastElementChild?.remove();
  }

  function normalizeText(value) {
    return String(value || "").toLowerCase().replace(/ё/g, "е");
  }

  function tokenize(value) {
    return normalizeText(value).match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)?/gu) || [];
  }

  function deriveTriggers(file) {
    const base = String(file).split("/").pop().replace(/\.[^.]+$/, "");
    return base.split(/[\s_-]+/).filter(Boolean);
  }

  function encodePath(path) {
    return String(path).split("/").map(part => encodeURIComponent(part)).join("/");
  }

  function buildAssetUrl(file) {
    const raw = String(file || "").trim();
    if (/^https?:\/\//i.test(raw)) return raw;
    if (raw.startsWith(`${settings.assetFolder}/`)) return encodePath(raw);
    return encodePath(`${settings.assetFolder}/${raw.replace(/^\/+/, "")}`);
  }

  const animations = (Array.isArray(rawConfig.animations) ? rawConfig.animations : []).map((item, index) => {
    const source = typeof item === "string" ? { file: item } : (item || {});
    const file = String(source.file || "").trim();
    const triggerLabels = Array.isArray(source.triggers) && source.triggers.length
      ? source.triggers.map(String).filter(Boolean)
      : deriveTriggers(file);
    return {
      id: `${index}:${file}`,
      file,
      url: buildAssetUrl(file),
      triggers: triggerLabels.map(label => ({ label, tokens: tokenize(label) })).filter(t => t.tokens.length),
      durationMs: Number.isFinite(Number(source.durationMs)) && Number(source.durationMs) > 0 ? Number(source.durationMs) : null,
      loops: Math.max(1, Math.round(Number(source.loops) || 1)),
      resolvedDurationMs: null,
      durationPromise: null
    };
  }).filter(entry => entry.file && entry.triggers.length);

  function matchesAt(tokens, start, phraseTokens) {
    if (!phraseTokens.length || start + phraseTokens.length > tokens.length) return false;
    return phraseTokens.every((token, offset) => tokens[start + offset] === token);
  }

  function findAnimation(text) {
    const rawText = String(text || "");
    const tokens = tokenize(rawText);
    if (!tokens.length) return null;

    if (settings.commandsOnly) {
      if (!rawText.trimStart().startsWith("!")) return null;
      for (const entry of animations) {
        if (entry.triggers.some(trigger => matchesAt(tokens, 0, trigger.tokens))) return entry;
      }
      return null;
    }

    let best = null;
    animations.forEach((entry, entryIndex) => {
      for (const trigger of entry.triggers) {
        for (let i = 0; i < tokens.length; i += 1) {
          if (!matchesAt(tokens, i, trigger.tokens)) continue;
          const candidate = { entry, entryIndex, start: i, length: trigger.tokens.length };
          if (!best
            || candidate.start < best.start
            || (candidate.start === best.start && candidate.length > best.length)
            || (candidate.start === best.start && candidate.length === best.length && candidate.entryIndex < best.entryIndex)) {
            best = candidate;
          }
          break; // для этого триггера достаточно самого раннего совпадения
        }
      }
    });
    return best ? best.entry : null;
  }

  // --- Длительность Animated WebP -----------------------------------------
  function readU16LE(bytes, offset) {
    return bytes[offset] | (bytes[offset + 1] << 8);
  }
  function readU24LE(bytes, offset) {
    return bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
  }
  function readU32LE(bytes, offset) {
    return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;
  }
  function fourCC(bytes, offset) {
    return String.fromCharCode(bytes[offset], bytes[offset + 1], bytes[offset + 2], bytes[offset + 3]);
  }

  function parseWebPBuffer(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    if (bytes.length < 20 || fourCC(bytes, 0) !== "RIFF" || fourCC(bytes, 8) !== "WEBP") return null;
    let offset = 12;
    let cycleDurationMs = 0;
    let frameCount = 0;
    while (offset + 8 <= bytes.length) {
      const type = fourCC(bytes, offset);
      const size = readU32LE(bytes, offset + 4);
      const dataOffset = offset + 8;
      if (type === "ANMF" && dataOffset + 16 <= bytes.length) {
        cycleDurationMs += readU24LE(bytes, dataOffset + 12) || 100;
        frameCount += 1;
      }
      if (size > bytes.length) break;
      offset = dataOffset + size + (size % 2);
    }
    return frameCount && cycleDurationMs > 0 ? { cycleDurationMs, frameCount } : null;
  }

  async function fetchRange(url, start, end) {
    const response = await fetch(url, {
      headers: { Range: `bytes=${start}-${end}` },
      cache: "force-cache"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const contentRange = response.headers?.get?.("content-range") || "";
    const totalMatch = contentRange.match(/\/(\d+)$/);
    return {
      status: response.status,
      total: totalMatch ? Number(totalMatch[1]) : null,
      buffer: await response.arrayBuffer()
    };
  }

  async function parseWebPDuration(url) {
    const first = await fetchRange(url, 0, 11);
    if (first.status === 200) return parseWebPBuffer(first.buffer);

    const firstBytes = new Uint8Array(first.buffer);
    if (firstBytes.length < 12 || fourCC(firstBytes, 0) !== "RIFF" || fourCC(firstBytes, 8) !== "WEBP") return null;
    const total = first.total || readU32LE(firstBytes, 4) + 8;

    let offset = 12;
    let cycleDurationMs = 0;
    let frameCount = 0;
    while (offset + 8 <= total) {
      const headResult = await fetchRange(url, offset, Math.min(total - 1, offset + 23));
      if (headResult.status === 200) return parseWebPBuffer(headResult.buffer);
      const head = new Uint8Array(headResult.buffer);
      if (head.length < 8) break;
      const type = fourCC(head, 0);
      const size = readU32LE(head, 4);
      if (type === "ANMF" && head.length >= 24) {
        cycleDurationMs += readU24LE(head, 8 + 12) || 100;
        frameCount += 1;
      }
      if (size > total) break;
      offset += 8 + size + (size % 2);
    }
    return frameCount && cycleDurationMs > 0 ? { cycleDurationMs, frameCount } : null;
  }

  function resolveAutoDuration(entry) {
    if (entry.durationMs) return Promise.resolve(entry.durationMs);
    if (entry.resolvedDurationMs) return Promise.resolve(entry.resolvedDurationMs);
    if (!settings.autoDuration || !/\.webp(?:[?#]|$)/i.test(entry.url)) return Promise.resolve(null);
    if (!entry.durationPromise) {
      entry.durationPromise = parseWebPDuration(entry.url)
        .then(result => {
          if (!result?.cycleDurationMs) return null;
          entry.resolvedDurationMs = clamp(result.cycleDurationMs * entry.loops, 100, 120000);
          updateDurationLabel(entry);
          return entry.resolvedDurationMs;
        })
        .catch(error => {
          log(`Не удалось прочитать длительность ${entry.file}: ${error.message}. Используется значение по умолчанию.`);
          return null;
        });
    }
    return entry.durationPromise;
  }

  // --- Очередь воспроизведения --------------------------------------------
  const queue = [];
  const lastAnimationAt = new Map();
  const lastUserAt = new Map();
  const durationEls = new Map();
  let current = null;
  let currentPlayback = null;
  let playbackSequence = 0;
  let nextStartAt = 0;
  let processTimer = 0;

  function formatSeconds(ms) {
    return `${(ms / 1000).toFixed(ms % 1000 ? 1 : 0)} с`;
  }

  function updateDurationLabel(entry) {
    const el = durationEls.get(entry.id);
    if (!el) return;
    if (entry.durationMs) el.textContent = `${formatSeconds(entry.durationMs)} · задано вручную`;
    else if (entry.resolvedDurationMs) el.textContent = `${formatSeconds(entry.resolvedDurationMs)} · прочитано из WebP`;
    else el.textContent = `${formatSeconds(settings.defaultDurationMs)} · по умолчанию${settings.autoDuration ? ", уточнится при первом запуске" : ""}`;
  }

  function cleanUser(user) {
    return String(user || "").replace(/^@/, "").trim().slice(0, 40) || "зритель";
  }

  function enqueueAnimation(entry, meta = {}) {
    if (!entry) return false;
    const now = performance.now();
    const user = cleanUser(meta.user);
    const userKey = normalizeText(meta.login || user);

    if (!meta.bypassCooldown) {
      if (now - (lastAnimationAt.get(entry.id) || -1e15) < settings.sameAnimationCooldownMs) return false;
      if (userKey && now - (lastUserAt.get(userKey) || -1e15) < settings.perUserCooldownMs) return false;
    }
    if ((current && current.entry === entry) || queue.some(item => item.entry === entry)) return false;
    // maxQueue — число ожидающих анимаций, не считая ту, что начнётся прямо сейчас.
    const waitingLimit = current ? settings.maxQueue : settings.maxQueue + 1;
    if (queue.length >= waitingLimit) return false;

    queue.push({ entry, user, login: meta.login || "", platform: meta.platform || "manual" });
    if (!meta.bypassCooldown) {
      lastAnimationAt.set(entry.id, now);
      if (userKey) lastUserAt.set(userKey, now);
    }
    processQueue();
    return true;
  }

  function processQueue() {
    if (current || !queue.length) return;
    const delay = Math.max(0, nextStartAt - performance.now());
    if (delay > 0) {
      clearTimeout(processTimer);
      processTimer = setTimeout(processQueue, delay);
      return;
    }
    play(queue.shift());
  }

  function clearStageMedia() {
    stage?.querySelectorAll?.(".animation-media").forEach(el => el.remove());
    if (fallbackEl) fallbackEl.hidden = true;
  }

  function finishPlayback(playback) {
    if (!playback || playback.finished) return;
    playback.finished = true;
    clearTimeout(playback.hideTimer);
    clearTimeout(playback.loadTimer);
    if (currentPlayback !== playback) return;
    clearStageMedia();
    current = null;
    currentPlayback = null;
    nextStartAt = performance.now() + settings.globalCooldownMs;
    processQueue();
  }

  function play(item) {
    if (!item || !stage) return;
    current = item;
    const entry = item.entry;
    const playback = {
      id: ++playbackSequence,
      startedAt: performance.now(),
      hideTimer: 0,
      loadTimer: 0,
      finished: false
    };
    currentPlayback = playback;
    clearStageMedia();

    const fallbackDuration = entry.durationMs || entry.resolvedDurationMs || settings.defaultDurationMs;
    const scheduleHide = durationMs => {
      if (currentPlayback !== playback || playback.finished) return;
      clearTimeout(playback.hideTimer);
      const remaining = Math.max(100, playback.startedAt + clamp(durationMs, 100, 120000) - performance.now());
      playback.hideTimer = setTimeout(() => finishPlayback(playback), remaining);
    };

    const img = document.createElement("img");
    img.className = "animation-media";
    img.alt = "";
    img.decoding = "async";

    playback.loadTimer = setTimeout(() => {
      if (currentPlayback === playback) {
        log(`Файл ${entry.file} слишком долго загружается, пропуск.`);
        finishPlayback(playback);
      }
    }, 20000);

    img.addEventListener("load", () => {
      if (currentPlayback !== playback || playback.finished) return;
      clearTimeout(playback.loadTimer);
      playback.startedAt = performance.now();
      scheduleHide(fallbackDuration);
      log(`${item.user} → ${entry.file}`);
      void resolveAutoDuration(entry).then(duration => {
        if (duration && !entry.durationMs) scheduleHide(duration);
      });
    }, { once: true });

    img.addEventListener("error", () => {
      if (currentPlayback !== playback || playback.finished) return;
      clearTimeout(playback.loadTimer);
      log(`Не удалось загрузить ${entry.file}. Проверьте папку ${settings.assetFolder} и точное имя файла.`);
      if (showSetup && fallbackEl) {
        fallbackEl.textContent = `Тест: ${entry.file} — файл пока не найден в папке ${settings.assetFolder}`;
        fallbackEl.hidden = false;
        playback.startedAt = performance.now();
        scheduleHide(fallbackDuration);
      } else {
        finishPlayback(playback);
      }
    }, { once: true });

    // Фрагмент не отправляется на сервер и не ломает HTTP-кеш,
    // зато помогает браузеру начать анимированную картинку с первого кадра.
    img.src = `${entry.url}#play=${Date.now()}`;
    stage.appendChild(img);
  }

  function isIgnored(user, login) {
    return settings.ignoredUsers.has(String(user || "").toLowerCase())
      || settings.ignoredUsers.has(String(login || "").toLowerCase());
  }

  function handleChat(input = {}) {
    const user = cleanUser(input.user || input.username || input.displayName || input.login);
    const login = String(input.login || "").toLowerCase();
    const text = String(input.text || input.message || "").trim().slice(0, 500);
    if (!text || isIgnored(user, login)) return null;

    const entry = findAnimation(text);
    if (!entry) return null;
    const accepted = enqueueAnimation(entry, {
      user,
      login,
      platform: input.platform || "chat",
      bypassCooldown: Boolean(input.bypassCooldown)
    });
    if (!accepted && showSetup) log(`«${text}» от ${user}: анимация ${entry.file} пропущена (кулдаун или очередь).`);
    return accepted ? entry : null;
  }

  // --- Twitch IRC over WebSocket, анонимное чтение -------------------------
  function unescapeIrcTag(value) {
    const map = { s: " ", ":": ";", "\\": "\\", r: "\r", n: "\n" };
    return String(value).replace(/\\(.)/g, (_, c) => map[c] ?? c);
  }

  function parseTwitchLine(line) {
    let rest = String(line).replace(/\r$/, "");
    const tags = {};
    if (rest.startsWith("@")) {
      const space = rest.indexOf(" ");
      if (space < 0) return null;
      for (const part of rest.slice(1, space).split(";")) {
        const eq = part.indexOf("=");
        if (eq > 0) tags[part.slice(0, eq)] = unescapeIrcTag(part.slice(eq + 1));
      }
      rest = rest.slice(space + 1);
    }

    const marker = " PRIVMSG ";
    const idx = rest.indexOf(marker);
    if (idx < 0) return null;
    const login = rest.slice(0, idx).replace(/^:/, "").split("!")[0].toLowerCase();
    const after = rest.slice(idx + marker.length);
    const colon = after.indexOf(" :");
    if (colon < 0) return null;
    const text = after.slice(colon + 2)
      .replace(/^\x01ACTION\s+/i, "")
      .replace(/\x01$/, "");

    return {
      user: tags["display-name"] || login,
      login,
      text,
      channel: after.slice(0, colon).replace(/^#/, ""),
      platform: "twitch",
      tags
    };
  }

  let socket = null;
  let reconnectTimer = 0;
  let reconnectDelayMs = 1000;
  let connectionSequence = 0;

  function connectTwitch() {
    const sequence = ++connectionSequence;
    clearTimeout(reconnectTimer);
    if (socket) {
      const old = socket;
      socket = null;
      try { old.close(); } catch (_) {}
    }

    if (!channels.length) {
      setStatus("Twitch: канал не выбран");
      return;
    }
    const invalid = channels.filter(channel => !/^[a-z0-9_]{3,25}$/.test(channel));
    if (invalid.length) {
      setStatus(`Twitch: неверный логин канала: ${invalid.join(", ")}. Нужен логин из twitch.tv/ЛОГИН, без пробелов и @.`);
      return;
    }
    if (typeof WebSocket === "undefined") {
      setStatus("Twitch: WebSocket недоступен в этом браузере");
      return;
    }

    const nick = `justinfan${Math.floor(100000 + Math.random() * 900000)}`;
    let ws;
    try {
      ws = new WebSocket("wss://irc-ws.chat.twitch.tv:443");
    } catch (error) {
      setStatus(`Twitch: не удалось открыть WebSocket (${error.message})`);
      return;
    }
    socket = ws;
    setStatus(`Twitch: подключаемся к ${channels.map(c => `#${c}`).join(", ")}…`);

    ws.addEventListener("open", () => {
      if (sequence !== connectionSequence) return;
      ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands");
      ws.send("PASS anonymous");
      ws.send(`NICK ${nick}`);
      channels.forEach(channel => ws.send(`JOIN #${channel}`));
    });

    ws.addEventListener("message", event => {
      if (sequence !== connectionSequence) return;
      for (const line of String(event.data).split(/\r?\n/).filter(Boolean)) {
        if (line.startsWith("PING")) {
          ws.send("PONG :tmi.twitch.tv");
          continue;
        }
        if (line.includes(" RECONNECT")) {
          ws.close();
          continue;
        }
        if (line.includes(" 001 ")) {
          reconnectDelayMs = 1000;
          setStatus(`Twitch: слушаю ${channels.map(c => `#${c}`).join(", ")} (анонимно, только чтение)`);
        }
        const message = parseTwitchLine(line);
        if (message) handleChat(message);
      }
    });

    ws.addEventListener("error", () => {
      try { ws.close(); } catch (_) {}
    });

    ws.addEventListener("close", () => {
      if (sequence !== connectionSequence) return;
      socket = null;
      setStatus(`Twitch: соединение закрыто, переподключение через ${Math.round(reconnectDelayMs / 1000)} с…`);
      reconnectTimer = setTimeout(connectTwitch, reconnectDelayMs);
      reconnectDelayMs = Math.min(30000, reconnectDelayMs * 2);
    });
  }

  function setChannels(nextChannels, updateAddress = true) {
    channels = [...new Set(nextChannels.map(normalizeChannel).filter(Boolean))];
    if (channelInput) channelInput.value = channels.join(",");
    refreshObsUrl();
    if (updateAddress) {
      try {
        const url = new URL(window.location.href);
        if (channels.length) url.searchParams.set("channel", channels.join(","));
        else url.searchParams.delete("channel");
        if (showSetup) url.searchParams.set("setup", "1");
        window.history.replaceState(null, "", url.toString());
      } catch (_) {}
    }
    connectTwitch();
  }

  // --- Экран настройки -------------------------------------------------------
  function buildObsUrl() {
    const url = new URL(window.location.href);
    if (url.pathname.endsWith("/index.html")) url.pathname = url.pathname.slice(0, -"index.html".length);
    url.hash = "";
    url.search = "";

    if (channels.length) url.searchParams.set("channel", channels.join(","));
    if (settings.scalePercent !== 100) url.searchParams.set("scale", String(Math.round(settings.scalePercent)));
    if (settings.fit !== "contain") url.searchParams.set("fit", settings.fit);
    if (settings.align !== "center") url.searchParams.set("align", settings.align);
    if (settings.commandsOnly) url.searchParams.set("commandsOnly", "1");
    if (settings.defaultDurationMs !== (Number(rawConfig.defaultDurationMs) || 5000)) {
      url.searchParams.set("durationMs", String(Math.round(settings.defaultDurationMs)));
    }
    return url.toString();
  }

  function refreshObsUrl() {
    if (obsUrlInput) obsUrlInput.value = buildObsUrl();
  }

  function syncSetupInputsFromSettings() {
    if (channelInput) channelInput.value = channels.join(",");
    if (scaleInput) scaleInput.value = String(Math.round(settings.scalePercent));
    if (durationInput) durationInput.value = String(settings.defaultDurationMs / 1000);
    if (fitInput) fitInput.value = settings.fit;
    if (alignInput) alignInput.value = settings.align;
    if (commandsOnlyInput) commandsOnlyInput.checked = settings.commandsOnly;
    refreshObsUrl();
  }

  function renderAnimationList() {
    if (!animationListEl) return;
    animationListEl.innerHTML = "";
    durationEls.clear();
    for (const entry of animations) {
      const row = document.createElement("div");
      row.className = "animation-row";

      const info = document.createElement("div");
      const name = document.createElement("div");
      name.className = "animation-name";
      name.textContent = entry.file;
      const triggers = document.createElement("div");
      triggers.className = "animation-meta";
      triggers.textContent = `Слова: ${entry.triggers.map(t => t.label).join(", ")}`;
      const duration = document.createElement("div");
      duration.className = "animation-meta";
      durationEls.set(entry.id, duration);
      info.append(name, triggers, duration);

      const button = document.createElement("button");
      button.className = "secondary";
      button.type = "button";
      button.textContent = "Тест";
      button.addEventListener("click", () => {
        const accepted = enqueueAnimation(entry, { user: "Тест", platform: "test", bypassCooldown: true });
        log(accepted ? `Тест поставлен в очередь: ${entry.file}` : `Тест ${entry.file} уже играет или очередь заполнена.`);
      });

      row.append(info, button);
      animationListEl.appendChild(row);
      updateDurationLabel(entry);
    }
  }

  channelForm?.addEventListener("submit", event => {
    event.preventDefault();
    setChannels(parseChannels(channelInput?.value || ""));
  });

  scaleInput?.addEventListener("input", () => {
    settings.scalePercent = clamp(Number(scaleInput.value) || 100, 10, 100);
    applyVisualSettings();
    refreshObsUrl();
  });

  durationInput?.addEventListener("input", () => {
    settings.defaultDurationMs = clamp((Number(durationInput.value) || 5) * 1000, 300, 120000);
    animations.forEach(updateDurationLabel);
    refreshObsUrl();
  });

  fitInput?.addEventListener("change", () => {
    settings.fit = fitInput.value === "cover" ? "cover" : "contain";
    applyVisualSettings();
    refreshObsUrl();
  });

  alignInput?.addEventListener("change", () => {
    settings.align = alignInput.value;
    applyVisualSettings();
    refreshObsUrl();
  });

  commandsOnlyInput?.addEventListener("change", () => {
    settings.commandsOnly = Boolean(commandsOnlyInput.checked);
    refreshObsUrl();
  });

  copyUrlButton?.addEventListener("click", async () => {
    refreshObsUrl();
    const value = obsUrlInput?.value || "";
    try {
      await navigator.clipboard.writeText(value);
      copyUrlButton.textContent = "Скопировано";
      setTimeout(() => { copyUrlButton.textContent = "Копировать"; }, 1600);
    } catch (_) {
      obsUrlInput?.select();
      document.execCommand?.("copy");
    }
  });

  testChatForm?.addEventListener("submit", event => {
    event.preventDefault();
    const entry = handleChat({
      user: testUserInput?.value || "Viewer",
      text: testTextInput?.value || "",
      platform: "test"
    });
    if (!entry) log("Тест-чат: триггер не найден или сработал кулдаун.");
  });

  // Необязательный публичный интерфейс для своих интеграций.
  window.ChatAnimations = {
    handleChat,
    playFile(file, user = "") {
      const entry = animations.find(item => item.file === file);
      return entry ? enqueueAnimation(entry, { user, platform: "api" }) : false;
    },
    trigger(text, user = "") {
      return Boolean(handleChat({ user, text, platform: "api" }));
    },
    setChannel(channel) {
      setChannels(parseChannels(channel));
    },
    stop() {
      if (currentPlayback) finishPlayback(currentPlayback);
    },
    animations,
    _findAnimation: findAnimation,
    _parseTwitchLine: parseTwitchLine,
    _parseWebPBuffer: parseWebPBuffer
  };

  applyVisualSettings();
  renderAnimationList();
  syncSetupInputsFromSettings();
  connectTwitch();
})();
