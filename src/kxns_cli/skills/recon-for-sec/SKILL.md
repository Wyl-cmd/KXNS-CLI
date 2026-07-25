---
name: recon-for-sec
description: >-
  Entry P1 category router for reconnaissance and methodology. Use when mapping
  scope, discovering assets, fingerprinting technology, building endpoint
  inventory, choosing the first high-value security testing path, and planning
  industry-sector recon campaigns.
---

# Recon and Methodology Router

这是新目标和未知攻击面的起始入口。

## When to Use

- 你刚接一个新的目标，还不知道先测什么
- 你需要先做资产发现、技术识别、接口清点和测试路线规划
- 你想把后续测试建立在结构化方法论上，而不是随机枚举 payload
- 你需要规划批量行业侦查战役（sector-wide recon campaign）

## Skill Map

- [Insecure Source Code Management](../insecure-source-code-management/SKILL.md) — .git/.svn/.hg exposure detection
- [Dependency Confusion](../dependency-confusion/SKILL.md) — Supply chain reconnaissance for internal package names
- [Web Enumeration](../web-enumeration/SKILL.md) — Directory brute force, endpoint discovery, batch probe
- [Web2 Recon](../web2-recon/SKILL.md) — Per-target technical testing pipeline (httpx, WP enum, CORS, XMLRPC, port scan, JS analysis)
- [Recon SMB Services](../recon-smb-services/SKILL.md) — Sector-specific details for SMB service providers
- [WP Mass Recon](../wp-mass-recon/SKILL.md) — Batch WordPress reconnaissance at scale

## Recommended Flow

1. 先确认 in-scope 资产和目标类型
2. 再做资产发现、端口与服务识别、技术指纹与端点收集
3. 按收集到的现象再路由到 [api-recon-and-docs](../api-recon-and-docs/SKILL.md)、[hunt-auth-bypass](../hunt-auth-bypass/SKILL.md)、[injection-checking](../injection-checking/SKILL.md) 或 [business-logic-vulnerabilities](../business-logic-vulnerabilities/SKILL.md)

---

## Recon Hierarchy

```
Target Selection
└── Scope Definition (in-scope assets)
    └── Asset Discovery (subdomains, IPs, domains)
        └── Tech Fingerprinting (what's running)
            └── Endpoint Discovery (attack surface)
                └── Vulnerability Testing (per vulnerability type)
```

### Subdomain Enumeration (Critical First Step)

**Passive (no DNS queries to target):**
```bash
# Subfinder (aggregates multiple sources):
subfinder -d target.com -o subdomains.txt

# Amass passive:
amass enum -passive -d target.com

# Certsh (certificate transparency):
curl -s "https://crt.sh/?q=%.target.com&output=json" | jq -r '.[].name_value' | sort -u
```

**Active (DNS brute force + resolution):**
```bash
# Massdns + wordlist:
massdns -r /path/to/resolvers.txt -t A -o S -w output.txt \
  <(cat wordlist.txt | sed 's/$/.target.com/')

# ffuf for subdomain brute:
ffuf -w subdomains-wordlist.txt -u https://FUZZ.target.com \
  -mc 200,301,302,403 -H "Host: FUZZ.target.com"

# DNSx for bulk resolution:
cat subdomains.txt | dnsx -a -resp -o resolved.txt
```

### Service and Port Discovery

```bash
# Fast port scan (common ports):
nmap -T4 -F target.com -oN ports.txt

# httpx for HTTP probing:
cat subdomains.txt | httpx -title -tech-detect -status-code -o live_hosts.txt

# masscan for speed on large IP ranges:
masscan -p 80,443,8080,8443 10.0.0.0/8 --rate=1000
```

### Web Technology Fingerprinting

```bash
# Wappalyzer (browser extension) or:
whatweb https://target.com

# httpx with tech detection:
httpx -u https://target.com -tech-detect

# Check headers manually:
curl -sI https://target.com | grep -i "server\|x-powered-by\|x-generator"
```

**Fingerprint signals:**
- Server header: nginx/1.18, Apache/2.4, IIS/10.0
- X-Powered-By: PHP/7.4, ASP.NET
- Cookies: PHPSESSID (PHP), JSESSIONID (Java), _rails_session (Rails)
- HTML comments, meta generator, JS framework files

### Endpoint Discovery

```bash
# Directory brute force:
ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-files.txt \
  -mc 200,301,302,403 -t 50 -o dirs.txt

# feroxbuster (recursive):
feroxbuster -u https://target.com -w wordlist.txt -x php,html,txt -r

# Parameter discovery:
arjun -u https://target.com/api/endpoint

# JS source mining:
gau target.com | grep '\.js$' | httpx -mc 200 | xargs -I{} curl -s {} | \
  grep -oE '"/[a-zA-Z0-9/_-]+"' | sort -u

# Wayback URLs:
waybackurls target.com | sort -u > wayback_urls.txt
```

### API Endpoint Discovery

```
# Swagger/OpenAPI paths:
/swagger.json /api-docs /openapi.json /v2/api-docs /.well-known/ /docs/

# GraphQL paths:
/graphql /gql /v1/graphql /api/graphql
```

### Common Misconfigurations (Quick Wins)

```
□ CORS: Access-Control-Allow-Origin: * with credentials → CSRF + data theft
□ S3 bucket public: curl https://target.s3.amazonaws.com/
□ Directory listing: response contains "Index of /"
□ .git exposed: curl https://target.com/.git/config
□ .env exposed: curl https://target.com/.env
□ Debug mode: stack traces in production (source code exposure)
□ Default credentials: admin:admin, admin:password on admin panels
□ phpinfo.php: curl https://target.com/phpinfo.php
□ Backup files: config.bak, database.sql.gz, app.zip
□ GraphQL introspection enabled: POST /graphql {"query":"{__schema{types{name}}}"}
□ Admin panels: /admin /manager /console /phpmyadmin /wp-admin
```

### Quick Reference Tools

| Category | Tool |
|---|---|
| Subdomain enum | subfinder, amass, massdns |
| Port scan | nmap, masscan |
| HTTP probe | httpx |
| Dir brute | ffuf, feroxbuster, gobuster |
| JS mining | LinkFinder, gau, waybackurls |
| Secret scan | trufflehog, gitleaks |
| Parameter fuzz | arjun, x8 |
| Vuln scan | nuclei |
| Proxy/intercept | Burp Suite Pro |

---

## 通用行业分类侦查方法

本节提供适用于所有行业的标准化侦查模式。28 个行业特定的 `recon-*` 技能已被合并至此——使用下面的行业模板替换行业名和关键词即可覆盖任意行业。

### 行业适用侦查模式

所有行业的通用侦查流程包含四个维度：

| 维度 | 工具/来源 | 目标 |
|------|----------|------|
| 地理商业搜索 | Google Maps, Bing Maps | 按城市+行业关键词发现公司域名 |
| 商业列表平台 | Yelp, Pages Jaunes, Yellow Pages | 批量抓取公司名、网址、电话、地址 |
| 证书透明度 | crt.sh, subfinder | 从证书日志中发现行业相关域名 |
| 网站+邮箱枚举 | httpx + whois + hunter.io | 存活检测、技术指纹、联系人邮箱 |

#### 地理搜索模板

```bash
# Google Maps / Bing 地理搜索 — 按城市+行业抓取
# 搜索词模板: "[行业关键词] in [城市名]" 或 "[行业关键词] near me"
# 示例: "plumber in Austin TX", "dentist near Chicago IL"

# 使用 Yelp / Pages Jaunes 列表抓取:
# 1. 搜索行业+城市 → 获取商家列表页
# 2. 提取每个商家的: 名称、网址、电话、地址
# 3. 网址 → 存活检测 → 技术指纹 → 漏洞检测
```

#### 通用批量存活检测

```bash
# 从任意来源获得域名列表后:
cat domain_list.txt | httpx -silent -threads 50 -tech-detect -status-code -title -o alive.txt

# 提取 WordPress 目标:
grep -i 'wordpress' alive.txt > wp_alive.txt

# 对所有存活目标做快速 CORS + XMLRPC + 用户枚举:
while read -r url; do
  domain=$(echo "$url" | awk '{print $1}')
  # REST API users
  curl -sk --max-time 8 "https://$domain/wp-json/wp/v2/users" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)"
  # CORS
  curl -skI --max-time 5 "https://$domain/wp-json/wp/v2/users" -H "Origin: https://evil.com" | grep -i "access-control-allow"
  # XMLRPC
  curl -sk -o /dev/null -w "%{http_code}" --max-time 5 -X POST "https://$domain/xmlrpc.php"
done < wp_alive.txt
```

### 行业模板说明

将下面的 `{SECTOR_NAME}` 和 `{SECTOR_KEYWORD}` 替换为实际行业即可：

```markdown
## {SECTOR_NAME} Recon — Sector-Specific Guide

### Discovery Keywords
- crt.sh queries: "{SECTOR_KEYWORD}", "{SECTOR_KEYWORD} company"
- Domain patterns: "city{SECTOR_KEYWORD}.com", "{SECTOR_KEYWORD}pro.com"
- Google dorks: site:*.com "{SECTOR_KEYWORD}" "contact"

### Quick Probe Script
for t in $(cat {SECTOR_KEYWORD}-targets.txt); do
  echo "=== $t ==="
  curl -skI "https://$t/" | grep -iE "wordpress|php|wp-"
  curl -sk -o /dev/null -w "%{http_code}" "https://$t/wp-content/debug.log"
  curl -sk -o /dev/null -w "%{http_code}" "https://$t/wp-content/uploads/"
  curl -skI "https://$t/wp-json/wp/v2/users" -H "Origin: https://evil.com" | grep -i "access-control"
  echo "---"
done

### Attack Surface Signals (按行业定制)
- CMS: [WordPress / Wix / custom PHP / SaaS]
- Hosting: [shared / dedicated / CDN]
- Typical plugins: [WPForms / Elementor / booking system]
- Common PII vectors: [contact forms / booking / payment / insurance]
```

### 行业分级排名

基于对 600+ 美国公司跨 28 个行业的调研：

#### Tier 1 — 高产行业 (15-25% 漏洞率)

| 行业 | 漏洞率 | 最高频模式 | WordPress 率 | WAF 防护 | 最佳目标 |
|------|--------|-----------|-------------|----------|---------|
| 律师事务所 | 25% | CORS 凭证反射 | ~30% | 极少 | 独立/小型律所，GoDaddy 托管 |
| 园林绿化 | 20% | WP 用户枚举 | ~50% | 极少 | 本地 SMB，加盟模式 |
| 泳池服务 | 20% | WP 用户枚举 | ~45% | 极少 | 夏季季节性业务 |
| 害虫防治 | 20% | CORS | ~40% | 极少 | 加盟模式为主 |
| 屋顶维修 | 15% | WP 用户枚举 | ~45% | 极少 | 本地承包商 |
| 牙科诊所 | 15% | WP 用户枚举 | ~35% | 部分有 | 独立牙医诊所 |
| 健身房 | 15% | WP 用户枚举 | ~40% | 部分有 | CrossFit、瑜伽、武术 |
| 房地产 | 15% | CORS | ~40% | 部分有 | 独立经纪公司 |
| HVAC/水暖 | 14% | WP 用户枚举 + CORS | ~35% | 部分有 | 加盟模式，常有 staging |
| 物业管理 | 15% | CORS | ~30% | 部分有 | PII 密集型 |
| 汽车维修 | 11% | WP 用户枚举 | ~30% | 部分有 | 独立维修店 |
| 摄影 | 10% | WP 用户枚举 | ~50% | 部分有 | 作品集网站，通常 WP |

#### Tier 2 — 中产行业 (5-14% 漏洞率)

| 行业 | 漏洞率 | 备注 |
|------|--------|------|
| 清洁服务 | 13% | 地毯、窗户、霉菌修复 |
| 搬家公司 | 6% | WP 较少，SaaS 平台更多 |
| 会计/CPA | 5% | 部分受监管，金融数据风险 |
| 化粪池服务 | 25% 源码泄露 | .env, .git, wp-config 泄露率极高 |
| 洗窗服务 | 25% CORS | 小型作坊，DIY WP |
| 洗车店 | 20% 源码泄露 | Dockerfile, swagger, actuator 端点常见 |
| 面包店 | 18% CORS wildcard | 单个目标 28 个泄露文件 |
| 锁匠 | 20% WP 用户 + XMLRPC | 单个目标 38 个子域名 |
| 太阳能安装 | 极少 | 大品牌使用企业平台 |
| 烟囱清洁 | ~10% CORS + XMLRPC | 小型家庭业务 |
| 火灾修复 | ~10% | 加盟模式 (Servpro, Belfor) |
| 宠物美容 | 20% WP 用户 | Dogtopia, Camp Bow Wow |

#### Tier 3 — 零产/低产行业 (0-3% 漏洞率)

| 行业 | 漏洞率 | 原因 |
|------|--------|------|
| 汽车经销商 | 0% | 企业 CDK/Dealertrack 平台，非 WordPress |
| 保险 | 0% | 企业门户，重度 WAF |
| 旅行社 | 0% | SaaS (Sabre, Amadeus)，非自托管 |
| 银行/信用社 | 0% | GLBA 监管，强制安全 |
| 大型医疗 | 0% | HIPAA 监管，HITRUST 认证 |

**优先攻击 Tier 1 行业。跳过 Tier 3 行业**，除非你有特定情报表明存在 WordPress 使用。

### crt.sh 批量行业发现

```bash
# 使用 HTML 输出模式（JSON API 对宽泛查询不可靠）
SECTORS="roofing landscaping pestcontrol dentist gym fitness \
  cleaningservice movingcompany photography hvac \
  treeservice lawncare plumbing poolcleaning windowcleaning \
  barbershop daycare carpetcleaning handyman lawfirm \
  autorepair petgrooming autobody remodeling"

for sector in $SECTORS; do
  curl -s --max-time 40 "https://crt.sh/?q=${sector}&excluded=expired&dedup=Y" \
    -H 'User-Agent: Mozilla/5.0' 2>/dev/null | \
    grep -oE '>[A-Za-z0-9][A-Za-z0-9.-]*\.com<' | \
    sed 's/^>//;s/<$//' >> /tmp/all_crt_domains.txt
  sleep 2  # 避免被 rate limit
done

# 过滤噪音：排除子域名和基础设施域名
# 排除: autodiscover.*, vpn.*, api.*, mail.*, remote.*, webmail.*, crm.*, ftp.*
# 排除: cloudfront.net, awsdns-*, azurewebsites 等 CDN/云域名
```

### crt.sh 噪声过滤模式

```python
import re

skip_patterns = [
    '^autodiscover\\.', '^vpn\\.', '^api\\.', '^mail\\.', '^remote\\.',
    '^webmail\\.', '^crm\\.', '^ftp\\.', '^test\\.', '^dev\\.',
    '^exchange', '^hostmaster', '^owa\\.', '^smtp\\.',
]

SECTOR_KEYWORDS = {
    'roofing': ['roofing', 'roof', 'roofer'],
    'landscaping': ['landscaping', 'landscape', 'lawn'],
    'hvac': ['hvac', 'heating', 'cooling', 'air'],
    'dental': ['dentist', 'dental'],
    'pest-control': ['pest', 'mosquito'],
    'daycare': ['daycare'],
    'legal': ['lawfirm', 'law'],
    'fitness': ['gym', 'fitness'],
    'auto-repair': ['autorepair', 'auto', 'collision'],
    'cleaning': ['cleaning', 'maid'],
    'veterinary': ['vet', 'pet'],
    'pool-services': ['pool', 'spa'],
}
```

### 全国连锁品牌发现（Google 搜索）

对于由全国连锁品牌主导的行业（如牙科、健身房、面包店），域名名通常不含行业关键词，需使用 Google 搜索：

| 行业 | 搜索方法 | 连锁品牌示例 |
|------|---------|------------|
| 牙科连锁 | "top dental chains USA" | Aspen Dental, Gentle Dental, Coast Dental, DentalWorks, Heartland Dental |
| 健身房 | "largest fitness chains USA" | F45, Barry's, CrossFit, Gold's Gym, 24 Hour Fitness, LA Fitness, OrangeTheory |
| 面包店 | "largest bakery chains USA" | Cinnabon, Crumbl, Insomnia Cookies, Sprinkles, Nothing Bundt Cakes |
| 汽车钣金 | "auto body repair chains USA" | ABRA, Caliber, Gerber, Service King, Fix Auto |
| 地毯清洁 | "carpet cleaning companies USA" | Chem-Dry, ServPro, Stanley Steemer, Rainbow International |
| 洗衣服务 | "laundry delivery service USA" | Poplin, Rinse, Washlava, LaundryHeap |
| 日托 | "largest daycare chains USA" | Bright Horizons, KinderCare, Goddard, Primrose |
| 宠物美容 | "pet grooming chains USA" | Petco, PetSmart, Camp Bow Wow, Dogtopia |
| 害虫防治 | "pest control companies USA" | Terminix, Orkin, Ehrlich, Bulwark, Arrow |
| 树木服务 | "tree service companies USA" | Davey, SavATree, Arbor Care, Bartlett |

### Wave 扩展策略（来自跨波次实战）

#### Phase 1 — 覆盖率审计

在发现新目标之前，先了解已有的测试覆盖：

```bash
# 从已有目标文件中提取所有已测域名
ALL_TARGETS="/root/output/recon_us/new_targets/all_targets.txt"
grep -ohP '[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-z]{2,}' "$ALL_TARGETS" | sort -u > /tmp/targets_deduped.txt

# 检查每个行业已覆盖的 findings 文件数量
for sector in "dentist" "dental" "gym" "fitness" "baker" "roofing" "landscaping" "pest" "tree" "pet" "plumbing" "hvac"; do
  count=$(grep -l "$sector" /root/output/recon_us/new_targets/*_findings*.md 2>/dev/null | wc -l)
  echo "Sector '$sector': $count findings files"
done
```

#### Phase 2 — 批量存活检测

```bash
# 过滤已测域名，只保留新候选
grep -v -f /tmp/targets_deduped.txt /tmp/candidates.txt | sort -u > /tmp/fresh_candidates.txt

# 快速 curl 存活检测（~2.5 分钟 60 个目标）
for domain in $(cat /tmp/fresh_candidates.txt); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 8 "https://${domain}" 2>/dev/null)
  echo "$domain => $code"
done > /tmp/curl_alive.txt

grep -v "=> 000" /tmp/curl_alive.txt | cut -d' ' -f1 > /tmp/alive_domains.txt
```

#### Phase 3 — 全量测试流水线（批量 Python 脚本）

```python
#!/usr/bin/env python3
"""批量测试目标: httpx → WP REST → CORS → XMLRPC → ports"""
import subprocess, json, re

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except:
        return "ERROR"

def test_domain(domain, sector):
    findings = {"domain": domain, "sector": sector, "wp": False, "wp_users": 0,
                "cors_reflected": False, "xmlrpc_open": False}
    
    # STEP 1: httpx 探测
    r = run(f"httpx -sc -title -tech-detect -server -no-color -u https://{domain} -timeout 10")
    findings["http"] = r.strip()
    
    # STEP 2: WordPress REST API 检测
    for path in ["/wp-json/wp/v2/users", "/wp-json/", "/?rest_route=/wp/v2/users"]:
        r = run(f'curl -sk -o /dev/null -w "%{{http_code}}" --max-time 10 "https://{domain}{path}"')
        if r in ["200"]:
            findings["wp_rest_status"] = f"{path} => HTTP {r}"
            findings["wp"] = True
            user_resp = run(f'curl -sk --max-time 10 "https://{domain}{path}"', timeout=12)
            try:
                users = json.loads(user_resp)
                if isinstance(users, list):
                    findings["wp_users"] = len(users)
            except: pass
            break
    
    # STEP 3: CORS 检测
    target_url = f"https://{domain}/wp-json/wp/v2/users" if findings["wp"] else f"https://{domain}/"
    r = run(f'curl -sk -H "Origin: https://evil.com" -D- --max-time 10 "{target_url}" | grep -i access-control', timeout=12)
    if "Access-Control-Allow-Origin" in r:
        findings["cors_reflected"] = True
    
    # STEP 4: XMLRPC 检测
    r = run(f'curl -sk -o /dev/null -w "%{{http_code}}" --max-time 10 -X POST "https://{domain}/xmlrpc.php"', timeout=12)
    findings["xmlrpc_open"] = (r.strip() == "200")
    
    # STEP 5: 端口扫描 (top 20)
    r = run(f'nmap --top-ports 20 -T4 --open -n {domain}', timeout=120)
    ports = [line.split('/')[0] for line in r.split('\n') if re.search(r'^\d+/tcp\s+open', line)]
    findings["ports"] = ports
    
    # 严重程度评分
    score = sum([findings["wp"], bool(findings["wp_users"] > 0), findings["cors_reflected"], findings["xmlrpc_open"]])
    findings["vuln"] = "HIGH" if score >= 3 else ("MEDIUM" if score >= 2 else ("LOW" if score >= 1 else "NONE"))
    
    return findings
```

#### 高信号发现模式

| 模式 | 识别方法 | 严重程度 |
|------|---------|---------|
| **凭证 CORS** | `Access-Control-Allow-Origin: http://evil.com` + `Access-Control-Allow-Credentials: true` 在 `/wp-json/wp/v2/users` | HIGH |
| **WordPress 用户泄露** | REST API `/wp-json/wp/v2/users` 返回用户对象数组 | MEDIUM |
| **Wildcard CORS** | `Access-Control-Allow-Origin: *` (无凭证) | MEDIUM |
| **XMLRPC 开放** | `/xmlrpc.php` 返回 HTTP 200 | LOW-MEDIUM |
| **非标准端口开放** | 21 (FTP), 3306 (MySQL), 3389 (RDP), 5900 (VNC), 6379 (Redis) | 视情况 |

### 行业侦查常见陷阱

- **行业关键词重叠。** `pest control` 可能返回 `pestcontrol.com`（SaaS 平台，非害虫防治公司）。按 SMB 典型域名模式过滤。
- **crt.sh 返回 CDN/云端噪音。** `*.cloudfront.net` 或 `*.awsdns-*.org` 会出现在行业查询结果中。积极过滤。
- **crt.sh / subfinder 超时。** 对低流量行业或高峰期，API 经常挂起或返回空。回到手动收集已知美国公司列表：使用全国连锁排名、加盟商目录、行业协会成员列表。
- **行业饱和。** 每个行业扫描 50+ 目标后，你会看到重复模式。在基线建立后转入新行业。
- **企业 vs 加盟商。** 部分行业（HVAC、害虫防治）同时存在企业母公司域名和独立加盟商域名。加盟商域名是更软的目标。
- **停靠/待售域名产生大量误报。** 停靠域名对每个路径返回 HTTP 200。如果 `/robots.txt` 和 `/.env` 都返回 200 且 HTML title 相同（如 "This domain is for sale"），跳过该域名的所有后续检测。

---

## Recon Playbook — 4-Phase Pipeline

从 9 波次跨 600+ 美国公司域名的实战中提炼的最佳流水线。

### 4-Phase Pipeline 总览

| Phase | 名称 | 输入 | 工具 | 单目标耗时 | 输出 |
|-------|------|------|------|-----------|------|
| 0 | 目标生成 | 行业关键词, 域名列表 | subfinder, crt.sh | 2-5 min/行业 | `targets.txt` |
| 1 | 快速过滤 | `targets.txt` | httpx, curl (基础 WP 检查) | 2-3s/目标 | `alive.txt`, `wp_targets.txt` |
| 2 | WP 深度检测 | `wp_targets.txt` | CORS, XMLRPC, 用户, 泄露 | 30s/目标 | `findings.md` (per domain) |
| 3 | 深度入侵 | 评分 >= 6 的目标 | SSRF, 插件, 端口, JS, 错误日志 | 5-10 min/目标 | 完整渗透测试报告 |

### 严重程度评分 (Phase 2)

| 发现 | 分数 |
|------|------|
| WordPress 检测到 | +1 |
| REST API 用户暴露 | +2 per user |
| CORS 凭证反射 | +3 |
| XMLRPC system.multicall | +3 |
| 开放注册 | +2 |
| 源码泄露 (已验证) | +4 per leak |
| >= 3 个源码泄露 | +6 |

**升级阈值:** Score >= 6 → Phase 3 (深度入侵)

### 并行线程限制（实战经验值）

| 操作 | 最大线程数 | 原因 | 被封率 |
|------|-----------|------|--------|
| httpx 探测 | 50-100 | 轻量 HTTP 检测，I/O 密集型 | 0% |
| CORS 检测 | 20-30 | HEAD 请求，快速响应 | 0% |
| WP 用户枚举 | 10 | JSON 解析 + 每个目标输出 | 5% (curl UA) |
| XMLRPC 检测 | 5 | XML POST 含 body，较重型 | 高 (如顺序执行) |
| 源码泄露扫描 | 20-50 | 多路径 x 多目标，HEAD/GET | 5% |
| JS bundle 下载 | 2-3 | 大文件 (500KB+)，带宽密集型 | 0% |
| 错误日志下载 | 1 (顺序) | 巨大文件 (观察到的 896MB) | 间隔 30s |

### User-Agent 轮换（实战被封率）

| User Agent | 被封率 | 备注 |
|-----------|--------|------|
| Chrome/125 macOS | 0% (0/200) | 最佳选择 — 所有扫描使用此 UA |
| Chrome/125 Windows | 0% (0/200) | 与 macOS 持平 |
| curl/8.4 | 5% (10/200) | 被 GoDaddy/Cloudflare 封 |
| Python urllib | 15% (30/200) | 被 Cloudflare/WP Engine 封 |

### 托管服务商聚类

同一托管商上的站点共享相同的漏洞画像。按托管商匹配侦查深度：

| 托管商 | REST 用户 | readme.txt | CORS | XMLRPC | 最佳策略 |
|--------|-----------|------------|------|--------|---------|
| GoDaddy (无 CDN) | 通常暴露 | 通常可访问 | 经常反射 | 通常开放 | 完整 wp-mass-recon 流水线 |
| Cloudflare + WP Engine | 封堵 (401/403) | CDN 层封堵 | 可能可用 | 封堵 | 仅 CORS 扫描 + HTML 源码插件检测 |
| Hostinger | 暴露 | 可访问 | 经常反射 | 开放 | 完整流水线 |
| Bluehost | 暴露 | 可访问 | 经常反射 | 开放 | 完整流水线 |
| SiteGround | 混合 | 经常可访问 | 混合 | 混合 | 尝试所有方法，回退到 CORS |
| WP Engine (直连) | 封堵 (401) | 封堵 | 混合 | 封堵 | CORS 矩阵 + JS 密钥提取 |
| Vercel/Netlify | N/A (SPA) | N/A | Wildcard CORS 常见 | N/A | 源码泄露扫描 + JS 分析 |

### 限速规避

```bash
# HTTP/1.0 绕过部分 WAF
curl -sk --http1.0 "https://TARGET/path"

# 随机 2-4s jitter
sleep $(python3 -c "import random; print(round(random.uniform(2,4),1))")

# 使用 --resolve 绕过 CDN 直达源站
# curl -sk --resolve "example.com:443:ORIGIN_IP" "https://example.com/path"

# 对 WP Engine 使用 HTTP/1.0 绕过
curl -sk --http1.0 "https://TARGET/wp-json/wp/v2/users"
```

### 流水线陷阱

- **Phase 2 评分虚高。** 不要把 SPA catch-all 当作源码泄露。始终用模式匹配验证内容 (DB_, APP_, [core], CREATE TABLE, PHP Version)。
- **并行过载。** 50 个并发 curl 请求可能触发 WAF 封堵。从 10 个工作线程开始，逐步增加。
- **Phase 3 耗时。** 深度入侵每个目标需要 5-10 分钟。仅对评分 >= 6 的目标运行。
- **crt.sh 限速。** Phase 0 期间行业查询间隔 2-3 秒。
