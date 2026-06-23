import "./style.css";

const defaults = {
  github_url: "https://github.com/netspeedy/joflux",
  release_url: "https://github.com/netspeedy/joflux/releases",
  homebrew_url: "https://github.com/netspeedy/homebrew-joflux",
  latest_release: null,
};

function text(id, value) {
  const element = document.getElementById(id);
  if (element && value) {
    element.textContent = value;
  }
}

function href(id, value) {
  const element = document.getElementById(id);
  if (element && value) {
    element.href = value;
  }
}

function shortCommit(value) {
  return value ? value.slice(0, 12) : "main";
}

function formatDate(value) {
  if (!value) {
    return "Pending first release";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

async function loadMetadata() {
  try {
    const response = await fetch("./website-metadata.json", { cache: "no-store" });
    if (!response.ok) {
      return defaults;
    }
    return { ...defaults, ...(await response.json()) };
  } catch {
    return defaults;
  }
}

function applyMetadata(metadata) {
  const latest = metadata.latest_release;
  const releaseVersion = latest?.tag_name || "Not published yet";
  const releaseDate = formatDate(latest?.published_at);
  const releaseUrl = latest?.html_url || metadata.release_url;

  text("release-version", releaseVersion);
  text("release-date", releaseDate);
  text("release-commit", shortCommit(metadata.release_commit));
  text("footer-version", releaseVersion);

  href("nav-github-link", metadata.github_url);
  href("nav-releases-link", metadata.release_url);
  href("hero-docs-link", `${metadata.github_url}#readme`);
  href("install-release-link", releaseUrl);
  href("footer-release-link", metadata.release_url);

  href("nav-homebrew-link", metadata.homebrew_url);
  href("install-homebrew-link", metadata.homebrew_url);
  href("footer-homebrew-link", metadata.homebrew_url);
}

function setupTabs() {
  const tabs = [...document.querySelectorAll("[data-tab]")];
  const panels = [...document.querySelectorAll("[role='tabpanel']")];

  for (const tab of tabs) {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      for (const item of tabs) {
        const active = item === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
      }
      for (const panel of panels) {
        const active = panel.id === `panel-${target}`;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      }
    });
  }
}

setupTabs();
loadMetadata().then(applyMetadata);
