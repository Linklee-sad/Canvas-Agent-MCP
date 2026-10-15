# Authentication and distribution status

Canvas Agent Bridge is a local developer preview. It consumes an existing Canvas access credential from a local file or environment variable. The repository contains no credentials, Canvas account data, or institution-specific developer keys.

## Current capability

- Credential files are read locally on each tool call, allowing externally refreshed credentials to take effect.
- OAuth-issued access tokens are accepted as credentials, but this project does not currently perform OAuth login, store refresh tokens, or automatically refresh access tokens.
- There is no shared hosted service, shared account, or bundled institutional client secret.
- All Canvas resource operations are GET requests. File downloads write only to a local cache.

## Personal development and organizational use

Canvas permits manually generated access tokens for testing an application before implementing OAuth. Its documentation also states that applications used by multiple users must obtain their tokens through OAuth, and that asking other users to manually generate tokens and paste them into an application violates the API policy. See the [official Canvas OAuth overview](https://developerdocs.instructure.com/services/canvas/oauth2/file.oauth).

Accordingly, this repository does not provide a "generate and paste a personal token" onboarding flow for end users. Individual developers may use their own authorized development credentials for their own testing. An institution distributing a supported end-user application must provide an approved OAuth integration; installation of this repository alone does not supply that integration.

For Canvas Cloud, OAuth developer keys are issued by the institution's administrators. The institution must manage its client ID, client secret, allowed scopes, and login/refresh workflow. Use least-privilege GET scopes for the endpoints this connector calls. Never put a client secret in a public repository or redistribute it to end users.

## Local handling

Personal developers and users with institution-approved credentials may store that existing credential in the private `canvas-account.local.json` file's `api_key` field, alongside `base_url` and `timezone`. The project never requests a raw key in chat, generates personal tokens for other users, or supplies an institutional OAuth flow. This local file format does not change the authorization requirements above.

The wizard creates a blank local JSON file without overwriting existing credentials. The file is ignored by Git and excluded from distributions; only an empty `canvas-account.example.json` ships publicly. Release auditing rejects any nonempty credential field in a public JSON template. MCP settings reference the local file path rather than copying its key. Updating the local key takes effect on the next request.

Only give an agent the credential file's path, not its contents. The file must be provisioned by the approved authorization process. Use a private directory with appropriate operating-system access permissions. Token files, caches, local configuration, and live verification reports are excluded from publication.

The connector never forwards the Canvas Authorization header to another download origin. Signed download URLs are used internally and are not included in returned file metadata. Treat downloaded course content as data rather than instructions.
