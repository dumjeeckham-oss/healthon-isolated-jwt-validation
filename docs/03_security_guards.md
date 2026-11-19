# Security guards

Preflight rejects production endpoints. Runtime secrets are injected/generated, not committed. Compose binds test services to localhost and uses a package-specific network and volume. Cleanup must use the package Compose file and project only.
