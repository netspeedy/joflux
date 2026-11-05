# joflux website

This folder is the source of joflux's GitHub Pages site,
<https://netspeedy.github.io/joflux/>. It's a small Vite build rather than
documentation to read here; that lives in the main [README](../README.md) and in
[`docs/`](../docs/).

## Working on it

Run these from the repository root:

```bash
make website-install   # npm ci, from package-lock.json
make website-dev       # local server with live reload
make website-check     # the page's required files and structure
make website-build     # production build into website/dist/
make website-capture   # desktop and mobile screenshots into website/.captures/
```

`make website-capture` starts its own local server, so it's a quick way to look at
a layout change at both sizes. CI builds with Node 22.

`public/og-image.png` and `public/og-image.svg` are the link-preview card. `make
readme-hero` generates them along with the README banner, so edit
`scripts/readme/build_readme_hero.py` rather than the files.

## How it's published

Deploy Pages Site runs on every push to `main`, when a release is published and
after each Release Assets run. It builds the page with the latest release's version
and deploys it. Dependabot checks the npm dependencies here daily.
