import "@fontsource-variable/inter";
import "./style.css";

const defaultSiteURL = new URL("./", window.location.href).href;

const fallbackHighlights = [
  "Five-stage migration workflow: export, migrate, monitor, verify, archive",
  "Homebrew tap and source install for macOS, Linux, and any Python 3.11 host",
  "JSON state files at every step for retries, reporting, and audit handoff",
];

const defaultMetadata = {
  site_url: defaultSiteURL,
  github_repository: "netspeedy/joflux",
  github_url: "https://github.com/netspeedy/joflux",
  release_url: "https://github.com/netspeedy/joflux/releases",
  homebrew_url: "https://github.com/netspeedy/homebrew-joflux",
  docs_url: "https://github.com/netspeedy/joflux#readme",
  release_commit: "",
  latest_release: null,
};

function normalizeMetadata(metadata = {}) {
  return {
    ...defaultMetadata,
    ...metadata,
    site_url: `${metadata.site_url || defaultMetadata.site_url}`.replace(/\/?$/, "/"),
    github_url: metadata.github_url || defaultMetadata.github_url,
    release_url: metadata.release_url || defaultMetadata.release_url,
    homebrew_url: metadata.homebrew_url || defaultMetadata.homebrew_url,
    docs_url: metadata.docs_url || defaultMetadata.docs_url,
    release_commit: metadata.release_commit || "",
    latest_release: metadata.latest_release || null,
  };
}

function formatDate(value) {
  if (!value) {
    return "Not published yet";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }

  return `${new Intl.DateTimeFormat("en-GB", {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(parsed)} UTC`;
}

function shortCommit(value) {
  if (!value) {
    return "---";
  }

  return value.length > 10 ? value.slice(0, 7) : value;
}

function releaseCommit(metadata) {
  if (metadata.release_commit) {
    return metadata.release_commit;
  }

  const body = metadata.latest_release?.body || "";
  const match = body.match(/\/commit\/([0-9a-f]{7,40})/i);
  return match ? match[1] : "";
}

function stripMarkdown(value) {
  return value
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function releaseHighlights(metadata) {
  const release = metadata.latest_release;
  const body = release?.body || "";
  const lines = body.split("\n");
  const highlights = [];
  let inIncludedChanges = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (line === "## Included Changes") {
      inIncludedChanges = true;
      continue;
    }

    if (inIncludedChanges && line.startsWith("## ")) {
      break;
    }

    if (!inIncludedChanges || !line.startsWith("- ")) {
      continue;
    }

    const cleaned = stripMarkdown(line.slice(2)).replace(/\s+\([^)]*\)\s*$/, "");
    if (cleaned && !cleaned.startsWith("Automatically merged")) {
      highlights.push(cleaned);
    }

    if (highlights.length === 3) {
      break;
    }
  }

  if (highlights.length > 0) {
    return highlights;
  }

  if (release?.tag_name) {
    return [`Stable ${release.tag_name} release metadata is published`, ...fallbackHighlights.slice(1)];
  }

  return fallbackHighlights;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function setHref(id, value) {
  const element = document.getElementById(id);
  if (element && value) {
    element.href = value;
  }
}

function renderCommands(metadata) {
  setText("homebrew-command", "brew tap netspeedy/joflux\nbrew install joflux");
  setText(
    "source-command",
    metadata.latest_release?.tag_name
      ? `python3 -m venv .venv
source .venv/bin/activate
python -m pip install git+https://github.com/netspeedy/joflux@${metadata.latest_release.tag_name}`
      : `python3 -m venv .venv
source .venv/bin/activate
python -m pip install .`,
  );
  setText("env-command", `export JOFLUX_GITHUB_TOKEN="ghp_..."
export JOFLUX_FORGEJO_TOKEN="forgejo_..."`);
}

function renderMetadata(rawMetadata) {
  const metadata = normalizeMetadata(rawMetadata);
  const release = metadata.latest_release;
  const commit = shortCommit(releaseCommit(metadata));

  setHref("site-home-link", metadata.site_url);
  setHref("nav-github-link", metadata.github_url);
  setHref("nav-releases-link", metadata.release_url);
  setHref("nav-homebrew-link", metadata.homebrew_url);
  setHref("nav-docs-link", metadata.docs_url);
  setHref("hero-docs-link", metadata.docs_url);
  setHref("install-homebrew-link", metadata.homebrew_url);
  setHref("install-docs-link", metadata.docs_url);
  setHref("install-release-link", release?.html_url || metadata.release_url);
  setHref("footer-release-link", release?.html_url || metadata.release_url);
  setHref("footer-homebrew-link", metadata.homebrew_url);

  setText("release-version", release?.tag_name || "Awaiting release");
  setText("release-commit", commit);
  setText("release-date", formatDate(release?.published_at));
  setText("footer-version", release?.tag_name?.replace(/^v/, "") || "---");
  setText("footer-commit", commit);

  const highlightsList = document.getElementById("release-highlights");
  if (highlightsList) {
    highlightsList.replaceChildren(
      ...releaseHighlights(metadata).map((highlight) => {
        const item = document.createElement("li");
        item.textContent = highlight;
        return item;
      }),
    );
  }

  renderCommands(metadata);
}

async function loadMetadata() {
  renderMetadata(defaultMetadata);

  try {
    const response = await fetch("./website-metadata.json", { cache: "no-store" });
    if (response.ok) {
      renderMetadata(await response.json());
    }
  } catch {
    // Fall back to the defaults rendered above.
  }
}

function selectInstallTab(container, tabID) {
  container.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === tabID;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  container.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${tabID}`);
  });
}

function wireTabs() {
  document.querySelectorAll(".install-tabs").forEach((container) => {
    container.addEventListener("click", (event) => {
      const button = event.target.closest(".tab");
      if (!button) {
        return;
      }

      selectInstallTab(container, button.dataset.tab);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  wireTabs();
  void loadMetadata();
});
