# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it by opening a GitHub issue or contacting the maintainers directly. We take security seriously and will respond promptly.

## Data Access & Privacy

### What This Application Accesses

When authenticated, this MCP server can access:

- Your TIDAL user ID and account status
- Your favorite tracks, albums, and artists
- Your playlists (names, descriptions, and track lists)
- Search results from TIDAL's catalog
- Music recommendations based on your listening preferences

### Data Storage

**OAuth Tokens:**
- TIDAL OAuth session tokens are stored in your system's temporary directory
- Location: `<temp>/tidal-session-oauth.json`
- These tokens allow access to your TIDAL account and should be protected
- Tokens are refreshed automatically and expire according to TIDAL's policies

**No External Telemetry:**
- This application does not send your data to any third parties
- All API calls go directly to TIDAL's servers
- No analytics, tracking, or usage data is collected

### Network Security

- The Flask backend binds to `127.0.0.1` (localhost) only
- The service is not accessible from other machines on your network
- Default port is 5050, configurable via `TIDAL_MCP_PORT` environment variable

## Third-Party Dependencies

This project uses the following external libraries:

| Dependency | Purpose | Notes |
|------------|---------|-------|
| [tidalapi](https://github.com/tamland/python-tidal) | TIDAL API access | Community-maintained, not officially supported by TIDAL |
| [Flask](https://flask.palletsprojects.com/) | HTTP backend | Well-audited web framework |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | MCP protocol | Official Anthropic SDK |
| [requests](https://requests.readthedocs.io/) | HTTP client | Standard Python HTTP library |

**Optional:**
| Dependency | Purpose | Notes |
|------------|---------|-------|
| [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) | Download functionality | Separate tool with its own authentication |

## Best Practices for Users

1. **Protect your OAuth tokens** - Don't share your temp directory contents
2. **Use on trusted machines** - The localhost binding assumes your machine is secure
3. **Review tidal-dl-ng separately** - If using download features, audit that project independently
4. **Keep dependencies updated** - Run `uv sync` periodically to get security updates

## Supported Versions

Security updates are provided for the latest version only. We recommend always using the most recent release.
