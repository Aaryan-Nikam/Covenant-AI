const DEBUGGER_VERSION = "1.3";
const EXTENSION_VERSION = "0.1.4";
const DRIPIFY_HOME = "https://app.dripify.io/";
const attachedTabs = new Set();

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handleMessage(message)
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
  return true;
});

async function handleMessage(message) {
  switch (message?.type) {
    case "agent.version":
      return { version: EXTENSION_VERSION, tools: ["runUpload", "navigate", "screenshot", "click", "clickText", "clickTarget", "typeText", "scroll"] };
    case "agent.getActiveTab":
      return getActiveTab();
    case "agent.navigate":
      return navigate(message.url);
    case "agent.runUpload":
      return runUpload(message.job);
    case "agent.executeAction":
      return executeAction(message.action);
    case "agent.screenshot":
      return screenshot();
    case "agent.click":
      return click(message.x, message.y);
    case "agent.typeText":
      return typeText(message.text);
    case "agent.scroll":
      return scroll(message.deltaY ?? 500);
    case "agent.detach":
      return detachActiveTab();
    default:
      throw new Error(`Unknown message type: ${message?.type}`);
  }
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab.");
  return {
    id: tab.id,
    url: tab.url,
    title: tab.title,
    windowId: tab.windowId,
  };
}

async function activeTarget() {
  const tab = await getActiveTab();
  await attach(tab.id);
  return { tabId: tab.id };
}

async function attach(tabId) {
  if (attachedTabs.has(tabId)) {
    try {
      await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
      return;
    } catch {
      attachedTabs.delete(tabId);
    }
  }
  try {
    await chrome.debugger.attach({ tabId }, DEBUGGER_VERSION);
  } catch (error) {
    if (!String(error?.message || error).includes("Another debugger is already attached")) {
      throw error;
    }
  }
  attachedTabs.add(tabId);
  await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
}

async function detachActiveTab() {
  const tab = await getActiveTab();
  if (!attachedTabs.has(tab.id)) return { detached: false };
  await chrome.debugger.detach({ tabId: tab.id });
  attachedTabs.delete(tab.id);
  return { detached: true };
}

async function command(method, params = {}) {
  const target = await activeTarget();
  try {
    return await chrome.debugger.sendCommand(target, method, params);
  } catch (error) {
    if (String(error?.message || error).includes("Debugger is not attached")) {
      attachedTabs.delete(target.tabId);
      await attach(target.tabId);
      return chrome.debugger.sendCommand(target, method, params);
    }
    throw error;
  }
}

async function navigate(url) {
  if (!/^https:\/\/([^/]+\.)?dripify\.io\//.test(url)) {
    throw new Error("Navigation blocked: only Dripify URLs are allowed.");
  }
  await command("Page.enable");
  await command("Page.navigate", { url });
  return { navigated: true, url };
}

async function runUpload(job) {
  if (!job?.id) throw new Error("Select a queued upload job first.");
  const tab = await ensureDripifyTab(job.campaign_url || DRIPIFY_HOME);
  await attach(tab.id);
  await waitForTabComplete(tab.id);
  await chrome.debugger.sendCommand({ tabId: tab.id }, "Page.enable");
  const result = await chrome.debugger.sendCommand({ tabId: tab.id }, "Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  const visible = await chrome.debugger.sendCommand({ tabId: tab.id }, "Runtime.evaluate", {
    expression: `document.body ? document.body.innerText.slice(0, 6000) : ""`,
    returnByValue: true,
  });
  const clickables = await extractClickableTargets(tab.id);
  return {
    status: "ready",
    tabId: tab.id,
    url: tab.url,
    screenshotDataUrl: `data:image/png;base64,${result.data}`,
    visibleText: visible?.result?.value || "",
    clickableTargets: clickables,
    instruction: buildUploadInstruction(job),
  };
}

async function executeAction(action) {
  if (!action?.action_type) throw new Error("Missing action.");
  if (action.action_type === "click") {
    if (Number.isInteger(action.target_index)) return clickTarget(action.target_index);
    return click(action.x, action.y);
  }
  if (action.action_type === "click_target") return clickTarget(action.target_index);
  if (action.action_type === "click_text") return clickText(action.target_text || "");
  if (action.action_type === "type_text") return typeText(action.text || "");
  if (action.action_type === "scroll") return scroll(action.delta_y ?? 600);
  if (action.action_type === "wait") {
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, action.seconds || 1) * 1000));
    return { waited: true };
  }
  return { skipped: true };
}

async function ensureDripifyTab(url) {
  if (!/^https:\/\/([^/]+\.)?dripify\.io\//.test(url)) {
    url = DRIPIFY_HOME;
  }
  const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (active?.id && /^https:\/\/([^/]+\.)?dripify\.io\//.test(active.url || "")) {
    if (active.url !== url && url !== DRIPIFY_HOME) {
      await chrome.tabs.update(active.id, { url, active: true });
    }
    return chrome.tabs.get(active.id);
  }
  const tabs = await chrome.tabs.query({ url: ["https://app.dripify.io/*", "https://*.dripify.io/*"] });
  if (tabs[0]?.id) {
    await chrome.tabs.update(tabs[0].id, { active: true, url });
    return chrome.tabs.get(tabs[0].id);
  }
  return chrome.tabs.create({ url, active: true });
}

function waitForTabComplete(tabId) {
  return new Promise((resolve) => {
    chrome.tabs.get(tabId, (tab) => {
      if (tab?.status === "complete") return resolve();
      const listener = (updatedTabId, changeInfo) => {
        if (updatedTabId === tabId && changeInfo.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }, 5000);
    });
  });
}

function buildUploadInstruction(job) {
  return [
    "Follow the observation protocol: inspect visible clickable targets first, then the screenshot, then visible text, then decide one action.",
    "Assess the visible Dripify page and decide the clicks needed to upload leads for the selected campaign.",
    `Campaign: ${job.campaign_name || "selected/configured campaign"}`,
    `CSV path on local machine: ${job.csv_path}`,
    "Goal: reach the Dripify import/upload leads flow, upload this CSV, map obvious fields, and complete import.",
    "Do not change campaign settings, limits, messages, billing, integrations, or delete anything.",
    "Stop if login, 2FA, CAPTCHA, billing, permissions, or ambiguous campaign selection appears."
  ].join("\n");
}

async function screenshot() {
  await command("Page.enable");
  const result = await command("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  return {
    dataUrl: `data:image/png;base64,${result.data}`,
  };
}

async function click(x, y) {
  assertNumber(x, "x");
  assertNumber(y, "y");
  await command("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x,
    y,
    button: "left",
    clickCount: 1,
  });
  await command("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x,
    y,
    button: "left",
    clickCount: 1,
  });
  return { clicked: true, x, y };
}

async function typeText(text) {
  if (typeof text !== "string") throw new Error("text must be a string.");
  await command("Input.insertText", { text });
  return { typed: true, length: text.length };
}

async function scroll(deltaY) {
  assertNumber(deltaY, "deltaY");
  await command("Input.dispatchMouseEvent", {
    type: "mouseWheel",
    x: 300,
    y: 300,
    deltaX: 0,
    deltaY,
  });
  return { scrolled: true, deltaY };
}

function assertNumber(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number.`);
  }
}

async function clickText(targetText) {
  if (!targetText) throw new Error("target_text is required.");
  const escaped = targetText.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
  const result = await command("Runtime.evaluate", {
    expression: `
      (() => {
        const wanted = "${escaped}".toLowerCase().trim();
        const tokens = wanted.split(/[|,>/]+/).map((part) => part.trim()).filter(Boolean);

        const visible = (el) => {
          if (!el || !(el instanceof HTMLElement)) return false;
          const style = getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            Number.parseFloat(style.opacity || '1') > 0 &&
            rect.width >= 8 &&
            rect.height >= 8
          );
        };

        const labelOf = (el) => (
          (el.getAttribute('aria-label') ||
            el.getAttribute('title') ||
            el.getAttribute('alt') ||
            el.value ||
            el.innerText ||
            el.textContent ||
            '').trim()
        );

        const isClickable = (el) => {
          if (!el || !(el instanceof HTMLElement)) return false;
          const style = getComputedStyle(el);
          return (
            el.matches('button, a, input[type="button"], input[type="submit"], summary, [role="button"]') ||
            el.hasAttribute('onclick') ||
            el.tabIndex >= 0 ||
            style.cursor === 'pointer'
          );
        };

        const clickableAncestor = (el) => {
          let node = el;
          for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
            if (isClickable(node)) return node;
          }
          return null;
        };

        const scoreLabel = (label) => {
          const text = label.toLowerCase();
          if (!text) return 0;
          let score = 0;
          for (const token of tokens.length ? tokens : [wanted]) {
            if (!token) continue;
            if (text === token) score += 120;
            else if (text.startsWith(token)) score += 90;
            else if (text.includes(token)) score += 70;
            else if (token.includes(text)) score += 50;
          }
          if (wanted.includes('campaign')) {
            if (text.includes('draft')) score += 55;
            if (text.includes('new campaign')) score += 35;
            if (text.includes('campaign')) score += 20;
          }
          if (wanted.includes('lead') || wanted.includes('upload') || wanted.includes('import')) {
            if (text.includes('lead')) score += 50;
            if (text.includes('upload')) score += 50;
            if (text.includes('import')) score += 50;
            if (text.includes('add')) score += 20;
          }
          return score;
        };

        const scored = [];
        for (const node of Array.from(document.querySelectorAll('*'))) {
          if (!visible(node)) continue;
          const label = labelOf(node);
          const score = scoreLabel(label);
          if (!score) continue;
          const target = clickableAncestor(node) || node;
          const rect = target.getBoundingClientRect();
          scored.push({
            score: score + (isClickable(target) ? 15 : 0) + Math.min(20, Math.max(0, rect.width / 50)) + Math.min(10, Math.max(0, rect.height / 40)),
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            label,
          });
        }

        scored.sort((a, b) => b.score - a.score);
        const match = scored[0];
        if (!match) {
          const fallback = Array.from(document.querySelectorAll('*'))
            .filter((el) => visible(el) && isClickable(el))
            .map((el) => {
              const rect = el.getBoundingClientRect();
              const label = labelOf(el).toLowerCase();
              let score = rect.width * rect.height;
              if (label.includes('new campaign')) score += 10000;
              if (wanted.includes('campaign') && label.includes('draft')) score += 9000;
              if (wanted.includes('campaign') && label.includes('campaign')) score += 4000;
              if (wanted.includes('lead') && (label.includes('upload') || label.includes('import') || label.includes('add'))) score += 9000;
              if (rect.top > 120) score += 1000;
              return { score, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, label };
            })
            .sort((a, b) => b.score - a.score)[0];
          if (!fallback) return { found: false };
          return { found: true, x: fallback.x, y: fallback.y, label: fallback.label, fallback: true };
        }
        return { found: true, x: match.x, y: match.y, label: match.label };
      })();
    `,
    returnByValue: true,
  });
  const value = result?.result?.value;
  if (!value?.found) throw new Error(`Could not find clickable text: ${targetText}`);
  return click(Math.round(value.x), Math.round(value.y));
}

async function clickTarget(targetIndex) {
  if (!Number.isInteger(targetIndex) || targetIndex < 0) {
    throw new Error("target_index must be a non-negative integer.");
  }
  const targets = await extractClickableTargets((await getActiveTab()).id);
  const target = targets[targetIndex];
  if (!target) {
    throw new Error(`Clickable target index ${targetIndex} not found.`);
  }
  return click(Math.round(target.x), Math.round(target.y));
}

async function extractClickableTargets(tabId) {
  const response = await chrome.debugger.sendCommand({ tabId }, "Runtime.evaluate", {
    expression: `
      (() => {
        const isVisible = (el) => {
          if (!el || !(el instanceof HTMLElement)) return false;
          const style = getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            Number.parseFloat(style.opacity || '1') > 0 &&
            rect.width >= 8 &&
            rect.height >= 8
          );
        };
        const labelOf = (el) => (
          (el.getAttribute('aria-label') ||
            el.getAttribute('title') ||
            el.getAttribute('alt') ||
            el.value ||
            el.innerText ||
            el.textContent ||
            '').trim()
        );
        const clickable = Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"], summary, [role="button"], [onclick], [tabindex]'))
          .filter((el) => isVisible(el))
          .map((el) => {
            const rect = el.getBoundingClientRect();
            const text = labelOf(el).replace(/\\s+/g, ' ').trim();
            return {
              text: text.slice(0, 120),
              ariaLabel: (el.getAttribute('aria-label') || '').slice(0, 120),
              title: (el.getAttribute('title') || '').slice(0, 120),
              role: (el.getAttribute('role') || '').slice(0, 60),
              tagName: el.tagName.toLowerCase(),
              x: Math.round(rect.left + rect.width / 2),
              y: Math.round(rect.top + rect.height / 2),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            };
          })
          .filter((item) => item.x >= 0 && item.y >= 0)
          .slice(0, 60);
        return clickable;
      })();
    `,
    returnByValue: true,
  });
  return response?.result?.value || [];
}
