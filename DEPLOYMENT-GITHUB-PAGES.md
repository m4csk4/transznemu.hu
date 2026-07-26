# Deployment — GitHub Pages

An alternative to the nginx-behind-Cloudflare setup in [DEPLOYMENT.md](DEPLOYMENT.md).
Here GitHub builds the Hugo site and serves it from GitHub Pages, with GitHub
Actions handling both deploys and the periodic OpenStreetMap data refresh — no
server to run.

```text
push to main ─┐
              ├─▶ Actions: build (Hugo) ─▶ upload artifact ─▶ Pages CDN ─▶ visitor
weekly cron ──┘   (refresh job commits data/budik.json first, then triggers a deploy)
```

Two workflows drive this:

| Workflow | File | Trigger | Does |
| -------- | ---- | ------- | ---- |
| Deploy to GitHub Pages | [.github/workflows/deploy.yml](.github/workflows/deploy.yml) | push to `main`, manual | Builds with Hugo, publishes to Pages. |
| Refresh OSM toilet data | [.github/workflows/refresh-osm.yml](.github/workflows/refresh-osm.yml) | weekly cron, manual | Re-runs `fetch-budik.sh`, commits `data/budik.json` if it changed, then triggers a deploy. |

## One-time setup

1. **Push the repo to GitHub** (the theme is a submodule; the workflow checks it
   out with `submodules: recursive`, so nothing else is needed).

2. **Enable Pages from Actions.** Repo → **Settings → Pages → Build and
   deployment → Source → GitHub Actions**. This is required — the workflow
   deploys via `actions/deploy-pages`, not from a branch. No `gh-pages` branch
   is created.

3. **Grant workflow write permissions.** Repo → **Settings → Actions → General →
   Workflow permissions → Read and write permissions**. The refresh job needs
   this to commit the updated data and to dispatch the deploy.

That's enough for the default `https://<owner>.github.io/<repo>/` URL. For the
real domain, do the custom-domain step below as well.

## Custom domain (transznemu.hu)

Set the domain in **Settings → Pages → Custom domain** → `transznemu.hu`, then
point DNS at GitHub. Two ways, depending on whether you keep Cloudflare in front:

**A. DNS straight to GitHub Pages** (simplest). At your DNS provider:

```text
# apex (transznemu.hu)
A     transznemu.hu   185.199.108.153
A     transznemu.hu   185.199.109.153
A     transznemu.hu   185.199.110.153
A     transznemu.hu   185.199.111.153
AAAA  transznemu.hu   2606:50c0:8000::153
AAAA  transznemu.hu   2606:50c0:8001::153
AAAA  transznemu.hu   2606:50c0:8002::153
AAAA  transznemu.hu   2606:50c0:8003::153
# www (optional)
CNAME www             <owner>.github.io.
```

Wait for the DNS check in Settings → Pages to go green, then tick **Enforce
HTTPS** (GitHub provisions the cert automatically once the domain verifies).

**B. Keep Cloudflare in front.** Use the same records above as Cloudflare DNS
entries. To let GitHub issue its cert:

- First set the records **DNS-only (grey cloud)** and enable **Enforce HTTPS**
  in Pages settings. GitHub can only provision the Let's Encrypt cert when it can
  reach the origin directly, so it must not be proxied at that moment.
- Once the cert is issued, you may switch to **proxied (orange cloud)** and set
  Cloudflare SSL/TLS mode to **Full**. Leave it grey if you prefer to skip
  Cloudflare's proxy entirely.

The `baseURL` is handled automatically — the build passes
`--baseURL "${{ steps.pages.outputs.base_url }}/"`, which resolves to the custom
domain when one is configured and to the `github.io` project URL otherwise. You
do **not** need to edit [config/\_default/hugo.toml](config/_default/hugo.toml).

## How the deploy works

[.github/workflows/deploy.yml](.github/workflows/deploy.yml) installs Hugo
extended (pinned via `HUGO_VERSION` — keep it in step with the version in
[DEPLOYMENT.md](DEPLOYMENT.md)), checks out the theme submodule, builds with
`hugo --gc --minify`, uploads `public/` as a Pages artifact, and deploys it.

It runs on every push to `main` and can be triggered manually from the **Actions**
tab (**Run workflow**). Because production is the default Hugo environment
(`config/_default`), no `--environment` flag is needed — the dev/staging build
from the nginx guide has no equivalent here.

## How the periodic OSM refresh works

[.github/workflows/refresh-osm.yml](.github/workflows/refresh-osm.yml) runs weekly
(Mondays 03:00 UTC) and on demand. It:

1. Runs [scripts/fetch-budik.sh](scripts/fetch-budik.sh) (curl + jq are
   preinstalled on the runner) to rewrite `data/budik.json` from Overpass.
2. Commits and pushes the file **only if it changed**.
3. Triggers the Deploy workflow so the fresh data ships.

Step 3 is deliberate: a push made with the built-in `GITHUB_TOKEN` does **not**
fire the `push` event (GitHub blocks that to prevent recursive runs), so the
`Deploy` workflow wouldn't start on its own. `workflow_dispatch` *is* allowed
from `GITHUB_TOKEN`, so the job calls `gh workflow run deploy.yml` to launch it.

Adjust the cadence by editing the `cron:` line — e.g. `0 3 1 * *` for monthly.
If an Overpass call times out or is rate-limited, the job fails and commits
nothing; the next scheduled run retries. `data/budik.json` stays committed (as in
the nginx setup) so the site always builds without a live Overpass call.

## Notes vs. the nginx setup

- **No Cloudflare-only access control.** GitHub Pages is public by design; the
  `deny all` / edge-IP allow-listing from the nginx config has no equivalent.
- **No separate dev/staging site.** Add a second workflow building
  `--environment development` to a preview target if you need one, or use
  `hugo server --environment development` locally.
- The Cloudflare-IP refresh script and nginx snippets are irrelevant here and can
  be left in place for the nginx deployment.
