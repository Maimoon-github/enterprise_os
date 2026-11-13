/**
 * The Options page: lets someone running their own AgentSDR add its address.
 * Adding one asks Chrome for access to that site (optional_host_permissions)
 * and stores it; background.ts then injects the bridge there. Removing one
 * gives the permission back.
 */
import { BUILT_IN_ORIGINS, customOrigins, normalizeOrigin, originPattern, saveCustomOrigins } from "./origins";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function setStatus(text: string, tone: "ok" | "error" | "" = ""): void {
  const status = $("status");
  status.textContent = text;
  status.className = tone;
}

function row(origin: string, removable: boolean): HTMLLIElement {
  const li = document.createElement("li");
  const label = document.createElement("span");
  label.textContent = origin;
  li.append(label);
  if (removable) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => void removeOrigin(origin));
    li.append(remove);
  } else {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "built in";
    li.append(tag);
  }
  return li;
}

async function render(): Promise<void> {
  const custom = await customOrigins();
  $("custom").replaceChildren(...custom.map((origin) => row(origin, true)));
  $("none").hidden = custom.length > 0;
  $("builtin").replaceChildren(...BUILT_IN_ORIGINS.map((origin) => row(origin, false)));
}

async function addOrigin(input: string): Promise<void> {
  const origin = normalizeOrigin(input);
  if (!origin) {
    setStatus("That is not an AgentSDR address. Use https://, for example https://sdr.yourcompany.com.", "error");
    return;
  }
  if (BUILT_IN_ORIGINS.includes(origin) || (await customOrigins()).includes(origin)) {
    setStatus(`${origin} is already allowed.`, "ok");
    return;
  }
  // Must run in the click's user gesture: Chrome shows its own prompt.
  const granted = await chrome.permissions.request({ origins: [originPattern(origin)] });
  if (!granted) {
    setStatus(`Chrome did not allow access to ${origin}, so it was not added.`, "error");
    return;
  }
  await saveCustomOrigins([...(await customOrigins()), origin]);
  setStatus(`Added ${origin}. Reload any open AgentSDR tab there.`, "ok");
  ($("origin") as HTMLInputElement).value = "";
  await render();
}

async function removeOrigin(origin: string): Promise<void> {
  await saveCustomOrigins((await customOrigins()).filter((value) => value !== origin));
  await chrome.permissions.remove({ origins: [originPattern(origin)] }).catch(() => false);
  setStatus(`Removed ${origin}.`, "ok");
  await render();
}

$("add").addEventListener("submit", (event) => {
  event.preventDefault();
  void addOrigin(($("origin") as HTMLInputElement).value);
});

void render();
