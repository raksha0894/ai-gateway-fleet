## Security Architecture – AI Gateway Fleet OTA

1. Overview

This document describes the security model of the AI Gateway Fleet OTA system, focusing on:
	•	Artifact integrity
	•	Authenticity verification
	•	Offline-first validation
	•	Rollback safety
	•	Threat mitigation
	•	Key management and rotation

The system is designed to operate securely under intermittent connectivity and fully offline robot environments.


2. Security Goals

The system is designed to guarantee:
	1.	Integrity – OTA packages cannot be modified without detection.
	2.	Authenticity – Only trusted publishers can issue updates.
	3.	Offline Verification – Robots verify updates without internet access.
	4.	Resilience – Failed or malicious updates are rolled back automatically.
	5.	Least Trust – Robots never trust the internet or external sources directly.


3. Trust Model

Root of Trust

The system uses Cosign public/private key pairs as the root of trust.
	•	Private key: Used in CI / build pipeline
	•	Public key: Embedded in Gateway and Robot containers

CI / Publisher (private key)
        ↓
   Signed Artifacts
        ↓
Gateway / Robot (public key)

Robots and gateways trust only artifacts signed by the known public key.


4. Artifact Signing & Verification

4.1 Signing (CI / Build Stage)

During OTA package creation:
	1.	Application is packaged into .tar.gz
	2.	SHA256 checksum is computed
	3.	Cosign signs the artifact
	4.	Signature bundle is produced

Tools:
	•	cosign sign-blob

Outputs:
	•	app-vX.tar.gz
	•	app-vX.tar.gz.bundle
	•	app-vX.sha256
	•	manifest.json


4.2 Verification (Gateway & Robot)

Before installation, the robot performs:
	1.	SHA256 verification
	2.	Cosign signature verification

Example:

cosign verify-blob \
  --key cosign.pub \
  --bundle artifact.bundle \
  artifact.tar.gz

No network access is required.


5. Manifest Security

Each release includes a signed manifest:

{
  "version": "1.9.5",
  "artifact": "app-v1.9.5.tar.gz",
  "bundle": "app-v1.9.5.tar.gz.bundle",
  "sha256": "..."
}

Security properties:
	•	Immutable version mapping
	•	Strong checksum binding
	•	Signed artifact references
	•	Prevents downgrade/replay attacks

Robots never install packages not referenced by a valid manifest.


6. Threat Model

6.1 Threat Actors

Actor	                     Description
External Attacker	         MITM, malicious server
Compromised Gateway	         Tampered cache
Insider Threat	             Malicious signing
Network Attacker	         Replay/injection


6.2 Threats & Mitigations

Threat	                    Mitigation
Tampered OTA	            SHA256 + Cosign
MITM	                    Signature validation
Replay attack	            Version tracking
Malicious update	        Health check + rollback
Corrupt cache	            Re-verification
Partial download	        Resumable + checksum


7. Rollback & Safety

Each robot maintains:

/app/state/
  ├── current/
  ├── new/
  └── old/

Update flow:
	1.	Download → new/
	2.	Verify
	3.	Activate → current/
	4.	Run self-test
	5.	On failure → restore old/

Guarantees:
	•	No broken deployment persists
	•	Safe fallback


8. Telemetry Security

Current Design
	•	Robots send metrics over internal edge network
	•	Gateways buffer in SQLite
	•	Forward when online

Security properties:
	•	No direct internet exposure
	•	Limited attack surface
	•	Store-and-forward resilience

Future Hardening
	•	mTLS
	•	Message signing
	•	Auth tokens
	•	Gateway identity certs


9. Key Management & Rotation

Current Model
	•	Static cosign key pair
	•	Public key baked into containers
	•	Private key in CI environment

Rotation Process (Planned)
	1.	Generate new key pair
	2.	Publish new public key
	3.	Update containers
	4.	Dual-sign releases
	5.	Deprecate old key

Key v1 → Key v2 (overlap period) → Retire v1

Ensures zero-downtime rotation.


10. Offline Security Guarantees

Robots can fully verify updates while offline:
	•	Public key stored locally
	•	Bundled signatures
	•	Cached artifacts
	•	Local manifest

No external trust dependency exists at install time.


11. Future Security Architecture (Planned)

mTLS Communication

Robot ↔ Gateway ↔ Central
   (cert-authenticated)

	•	Mutual authentication
	•	Encrypted channels
	•	Revocable identities


Multi-Gateway Trust Federation
	•	Central CA
	•	Per-gateway certs
	•	Signed routing metadata


Secure Supply Chain
	•	Reproducible builds
	•	SLSA compliance
	•	Provenance verification
	•	Continuous attestation


Delta & Patch Signing
	•	Binary diffs
	•	Signed patches
	•	Reduced bandwidth
	•	Verified transitions

SBOM & Attestations
	•	SBOM and attestation files are generated during build
	•	Bundled with OTA artifacts
	•	Verified via cosign


