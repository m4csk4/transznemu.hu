# Deployment

How transznemu.hu is built and served. The site is a static [Hugo](https://gohugo.io/)
build served by nginx, with both the public site and a dev/staging site sitting
behind Cloudflare. nginx only accepts traffic from Cloudflare edge IPs.

```text
visitor ──▶ Cloudflare ──▶ nginx (Cloudflare-only) ──▶ static files
                            ├─ transznemu.hu      → public/
                            └─ dev.transznemu.hu  → public-dev/
```

## Prerequisites

- **Hugo extended** ≥ 0.163 (built with `v0.163.0+extended`). The PaperMod theme
  needs the *extended* edition.
- **nginx** with the `realip` module (standard in distro packages).
- **git** (the theme is a submodule).
- For the toilet-data refresh: **curl** and **jq**.

Clone with the theme submodule:

```bash
git clone <repo> transznemu.hu
cd transznemu.hu
git submodule update --init --recursive
```

## Environments

Hugo config is environment-based (`config/_default` + per-environment overrides):

| Environment | Build command                    | baseURL                      | Output        | nginx vhost         |
|-------------|----------------------------------|------------------------------|---------------|---------------------|
| production  | `hugo`                           | `https://transznemu.hu/`     | `public/`     | `transznemu.hu`     |
| development | `hugo --environment development` | `https://dev.transznemu.hu/` | `public-dev/` | `dev.transznemu.hu` |

The dev environment ([config/development/hugo.toml](config/development/hugo.toml))
also enables `buildDrafts` and `buildFuture`, so the staging site previews
unpublished content. Both outputs live in separate directories and never clobber
each other.

For local preview with live reload:

```bash
hugo server                            # production config
hugo server --environment development  # dev config (drafts + future posts)
```

## Building

```bash
# production
hugo --minify

# dev / staging
hugo --environment development --minify
```

`public/` and `public-dev/` are git-ignored — they are build artifacts, regenerate
them on the server rather than committing them.

## nginx

The vhost config lives in [nginx/](nginx/) and is meant to be symlinked into the
distro's `sites-enabled`:

```bash
sudo ln -s /root/transznemu.hu/nginx/transznemu.conf /etc/nginx/sites-enabled/transznemu.conf
sudo nginx -t
sudo systemctl reload nginx
```

Layout:

| File | Purpose |
| ---- | ------- |
| [nginx/transznemu.conf](nginx/transznemu.conf) | The two `server` blocks (prod + dev). |
| [nginx/snippets/site-common.conf](nginx/snippets/site-common.conf) | Shared serving + Cloudflare enforcement, included by both blocks. |
| [nginx/snippets/cloudflare-allow.conf](nginx/snippets/cloudflare-allow.conf) | `allow` rules for every Cloudflare range (access enforcement). |
| [nginx/snippets/cloudflare-realip.conf](nginx/snippets/cloudflare-realip.conf) | `set_real_ip_from` rules so logs show the real visitor IP. |

Roots are absolute paths to `public/` and `public-dev/`. If you deploy under a
different path, update the `root` directives and the `include` paths.

### Cloudflare-only access

Each vhost ends with `allow <every Cloudflare CIDR>; deny all;`, so any request
whose TCP peer is **not** a Cloudflare edge IP receives `403`. The visitor's real
IP is restored from the `CF-Connecting-IP` header (trusted only from Cloudflare
ranges), so access logs and rate limiting see the true client.

This means:

- **DNS for both `transznemu.hu` and `dev.transznemu.hu` must be proxied through
  Cloudflare** (orange cloud). A grey-cloud / direct record will be blocked.
- Set the Cloudflare SSL/TLS mode to **Full** (or Full-Strict if the origin has a
  cert). This config listens on port 80 only — TLS is terminated at Cloudflare.
  If the origin must serve HTTPS directly, add a `listen 443 ssl;` block with cert
  paths.

### Keeping Cloudflare IPs current

Cloudflare occasionally changes its published ranges. Refresh both snippets from
the source lists with:

```bash
./scripts/update-cloudflare-ips.sh
sudo nginx -t && sudo systemctl reload nginx
```

The ranges baked in were current as of 2026-06. Consider running the script on a
schedule (e.g. a monthly cron) so the allow-list never silently blocks legitimate
traffic.

## Data refresh (Budikereső map)

The toilet-finder map is driven by [data/budik.json](data/budik.json), generated
from the OpenStreetMap Overpass API:

```bash
./scripts/fetch-budik.sh   # rewrites data/budik.json
hugo --minify              # rebuild so the new data ships
```

Unlike the build outputs, `data/budik.json` **is** committed, so the site builds
without a live Overpass call. Re-run periodically to keep the map fresh.

## Full deploy checklist

```bash
git pull
git submodule update --init --recursive   # pick up theme changes
hugo --minify                              # → public/
hugo --environment development --minify    # → public-dev/
sudo nginx -t && sudo systemctl reload nginx
```

No service restart is needed for content-only changes — nginx serves the files
directly, so a fresh build is live immediately. Reload nginx only when the config
in `nginx/` changes.
