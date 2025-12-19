# TIDAL MCP: My Custom Picks 🌟🎧

> **Fork Notice**: This is a fork of [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) with added download functionality via [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) integration.

![Demo: Music Recommendations in Action](./assets/tidal_mcp_demo.gif)

Most music platforms offer recommendations — Daily Discovery, Top Artists, New Arrivals, etc. — but even with the state-of-the-art system, they often feel too "aggregated". I wanted something more custom and context-aware.

With TIDAL MCP, you can ask for things like:
> *"Based on my last 10 favorites, find similar tracks — but only ones from recent years."*
>
> *"Find me tracks like those in this playlist, but slower and more acoustic."*

The LLM filters and curates results using your input, finds similar tracks via TIDAL’s API, and builds new playlists directly in your account.

<a href="https://glama.ai/mcp/servers/@yuhuacheng/tidal-mcp">
  <img width="400" height="200" src="https://glama.ai/mcp/servers/@yuhuacheng/tidal-mcp/badge" alt="TIDAL: My Custom Picks MCP server" />
</a>

## Features

- 🌟 **Music Recommendations**: Get personalized track recommendations based on your listening history **plus your custom criteria**.
- ၊၊||၊ **Playlist Management**: Create, view, and manage your TIDAL playlists
- 📥 **Music Downloads**: Download tracks, albums, playlists, and favorites via tidal-dl-ng integration

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- TIDAL subscription
- (Optional, for downloads) [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) - Install with `pipx install tidal-dl-ng`

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yuhuacheng/tidal-mcp.git
   cd tidal-mcp
   ```

2. Create a virtual environment and install dependencies using uv:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the package with all dependencies from the pyproject.toml file:
   ```bash
   uv pip install --editable .
   ```

   This will install all dependencies defined in the pyproject.toml file and set up the project in development mode.

4. (Optional) Set up tidal-dl-ng for download functionality:
   ```bash
   # Install tidal-dl-ng
   pipx install tidal-dl-ng

   # Authenticate with TIDAL (opens browser for OAuth)
   tdn login
   ```

   **Note**: tidal-dl-ng uses its own authentication, separate from the MCP's TIDAL API auth. You'll need to authenticate both if you want to use all features.


## MCP Client Configuration

### Claude Desktop Configuration

To add this MCP server to Claude Desktop, you need to update the MCP configuration file. Here's an example configuration:
(you can specify the port by adding an optional `env` section with the `TIDAL_MCP_PORT` environment variable)

```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "/path/to/your/uv",
      "env": {
        "TIDAL_MCP_PORT": "5100"
      },
      "args": [
        "run",
        "--with",
        "requests",
        "--with",
        "mcp[cli]",
        "--with",
        "flask",
        "--with",
        "tidalapi",
        "mcp",
        "run",
        "/path/to/your/project/tidal-mcp/mcp_server/server.py"
      ]
    }
  }
}
```

Example scrrenshot of the MCP configuration in Claude Desktop:
![Claude MCP Configuration](./assets/claude_desktop_config.png)

### Steps to Install MCP Configuration

1. Open Claude Desktop
2. Go to Settings > Developer
3. Click on "Edit Config"
4. Paste the modified JSON configuration
5. Save the configuration
6. Restart Claude Desktop

## Suggested Prompt Starters
Once configured, you can interact with your TIDAL account through a LLM by asking questions like:

- *“Recommend songs like those in this playlist, but slower and more acoustic.”*
- *“Create a playlist based on my top tracks, but focused on chill, late-night vibes.”*
- *“Find songs like these in playlist XYZ but in languages other than English.”*

*💡 You can also ask the model to:*
- Use more tracks as seeds to broaden the inspiration.
- Return more recommendations if you want a longer playlist.
- Or delete a playlist if you're not into it — no pressure!

**Download Examples** (requires tidal-dl-ng):
- *"Download this track: 12345678"*
- *"Download the album with ID 87654321"*
- *"Download all my favorite tracks"*

## Available Tools

The TIDAL MCP integration provides the following tools:

**Core Tools:**
- `tidal_login`: Authenticate with TIDAL through browser login flow
- `get_favorite_tracks`: Retrieve your favorite tracks from TIDAL
- `recommend_tracks`: Get personalized music recommendations
- `create_tidal_playlist`: Create a new playlist in your TIDAL account
- `get_user_playlists`: List all your playlists on TIDAL
- `get_playlist_tracks`: Retrieve all tracks from a specific playlist
- `delete_tidal_playlist`: Delete a playlist from your TIDAL account

**Download Tools** (requires tidal-dl-ng):
- `download_track`: Download a single track by ID
- `download_album`: Download an entire album by ID
- `download_playlist`: Download all tracks from a playlist
- `download_favorites`: Download all favorites (tracks, albums, artists, or videos)

## License

[MIT License](LICENSE)

## Acknowledgements

- [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) - Original TIDAL MCP implementation
- [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) by exislow - TIDAL download functionality
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk)
- [TIDAL Python API](https://github.com/tamland/python-tidal)