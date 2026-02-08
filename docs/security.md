# Security Architecture – AI Gateway Fleet OTA

## Overview

This document describes the security model of the AI Gateway Fleet OTA system, focusing on:
1. Artifact integrity
2. Authenticity verification
3. Offline-first validation
4. Rollback safety
5. Threat mitigation
6. Key management and rotation

The system is designed to operate securely under intermittent connectivity and fully offline robot environments.


## Security Goals

The system is designed to guarantee:
1. Integrity – OTA packages cannot be modified without detection.
2. Authenticity – Only trusted publishers can issue updates.
3. Offline Verification – Robots verify updates without internet access.
4. Resilience – Failed or malicious updates are rolled back automatically.
5. Least Trust – Robots never trust the internet or external sources directly.


## Trust Model

### Root of Trust

The system uses Cosign public/private key pairs as the root of trust.
1. Private key: Used in CI / build pipeline
2. Public key: Embedded in Gateway and Robot containers

```text
CI / Publisher (private key)
        ↓
   Signed Artifacts
        ↓
Gateway / Robot (public key)
```
Robots and gateways trust only artifacts signed by the known public key.


## Artifact Signing & Verification

### Signing (CI / Build Stage)

During OTA package creation:
1. Application is packaged into .tar.gz
2. SHA256 checksum is computed
3. Cosign signs the artifact
4. Signature bundle is produced

#### Tools:
cosign sign-blob

#### Outputs:
1. app-vX.tar.gz
2. app-vX.tar.gz.bundle
3. app-vX.sha256
4. manifest.json


### Verification (Gateway & Robot)

Before installation, the robot performs:
1. SHA256 verification
2. Cosign signature verification

Example:
```text
cosign verify-blob \
  --key cosign.pub \
  --bundle artifact.bundle \
  artifact.tar.gz
```

No network access is required.


## Manifest Security

Each release includes a signed manifest:
```text
{
  "version": "1.9.5",
  "artifact": "app-v1.9.5.tar.gz",
  "bundle": "app-v1.9.5.tar.gz.bundle",
  "sha256": "..."
}
```
Security properties:
1. Immutable version mapping
2. Strong checksum binding
3. Signed artifact references
4. Prevents downgrade/replay attacks

Robots never install packages not referenced by a valid manifest.


## Threat Model

### Threat Actors

|Actor                |	         Description             |
|---------------------|----------------------------------|
|External Attacker    |	         MITM, malicious server  |
|Compromised Gateway  |          Tampered cache          |
|Insider Threat	      |          Malicious signing       |
|Network Attacker     |	         Replay/injection        |


### Threats & Mitigations

|Threat              |	    Mitigation                   |
|--------------------|-----------------------------------|
|Tampered OTA	     |      SHA256 + Cosign              |
|MITM	             |      Signature validation         |
|Replay attack	     |      Version tracking             |
|Malicious update    |	    Health check + rollback      |
|Corrupt cache	     |      Re-verification              |
|Partial download    |	    Resumable + checksum         |


### Rollback & Safety

Each robot maintains:
```text
/app/state/
  ├── current/
  ├── new/
  └── old/
```
#### Update flow:
1. Download → new/
2. Verify
3. Activate → current/
4. Run self-test
5. On failure → restore old/

#### Guarantees:
1. No broken deployment persists
2. Safe fallback


## Telemetry Security

### Current Design
1. Robots send metrics over internal edge network
2. Gateways buffer in SQLite
3. Forward when online

### Security properties:
1. No direct internet exposure
2. Limited attack surface
3. Store-and-forward resilience

### Future Hardening
1. mTLS
2. Message signing
3. Auth tokens
4. Gateway identity certs


## Key Management & Rotation

### Current Model
1. Static cosign key pair
2. Public key baked into containers
3. Private key in CI environment

### Rotation Process (Planned)
1. Generate new key pair
2. Publish new public key
3. Update containers
4. Dual-sign releases
5. Deprecate old key

```text
Key v1 → Key v2 (overlap period) → Retire v1
```
Ensures zero-downtime rotation.


## Offline Security Guarantees

Robots can fully verify updates while offline:
1. Public key stored locally
2. Bundled signatures
3. Cached artifacts
4. Local manifest

No external trust dependency exists at install time.


## Future Security Architecture (Planned)

### mTLS Communication
```text
Robot ↔ Gateway ↔ Central
   (cert-authenticated)
```
1. Mutual authentication
2. Encrypted channels
3. Revocable identities


### Multi-Gateway Trust Federation
1. Central CA
2. Per-gateway certs
3. Signed routing metadata


### Secure Supply Chain
1. Reproducible builds
2. SLSA compliance
3. Provenance verification
4. Continuous attestation


### Delta & Patch Signing
1. Binary diffs
2. Signed patches
3. Reduced bandwidth
4. Verified transitions

### SBOM & Attestations
1. SBOM and attestation files are generated during build
2. Bundled with OTA artifacts
3. Verified via cosign






