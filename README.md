# TIDAL DL MCP


This was originally a fork of [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp).  In addition to added Tidal search functionality and the ability to run [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) (if you have it installed), there have been other stability and performance improvements, including batch operations for large track lists.


## Features

- 🔍 **Music Search**: Search TIDAL's catalog for tracks, albums, and artists by name
- ⚡ **Batch Operations**: Search for multiple songs and create playlists efficiently in a single request
- 🌟 **Music Recommendations**: Get personalized track recommendations based on your listening history **plus your custom criteria**.
- ၊၊||၊ **Playlist Management**: Create, view, and manage your TIDAL playlists
- 📥 **Music Downloads**: Download tracks, albums, playlists, and favorites via [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) integration

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- TIDAL subscription
- (Optional, for downloads) [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) - Install with `pipx install tidal-dl-ng`

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/tidal-dl-mcp.git
   cd tidal-dl-mcp
   ```

2. **Important**: Do NOT create a virtual environment or run `uv pip install --editable .` in this directory. Claude Desktop uses `uv run` with `--with` flags to create an isolated environment automatically. Having a local `.venv` or editable install can cause version conflicts and hangs.

3. (Optional) Set up tidal-dl-ng for download functionality:
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

**Search Examples:**
- *"Search for Bohemian Rhapsody"*
- *"Find albums by Radiohead"*
- *"Look up the artist Daft Punk"*

**Recommendation Examples:**
- *"Recommend songs like those in this playlist, but slower and more acoustic."*
- *"Create a playlist based on my top tracks, but focused on chill, late-night vibes."*
- *"Find songs like these in playlist XYZ but in languages other than English."*

**Playlist Management Examples:**
- *"Add this track to my workout playlist"*
- *"Put these songs in my 90's playlist"*
- *"Show me all tracks in my road trip playlist"*

**Batch Playlist Creation Examples:**
- *"Create a playlist called 'Road Trip Mix' with these songs: Bohemian Rhapsody, Hotel California, Stairway to Heaven, Sweet Home Alabama"*
- *"Make me a workout playlist with 20 high-energy rock songs from the 80s"*
- *"Build a dinner party playlist with jazz standards like Take Five, So What, and My Favorite Things"*

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
- `search_tidal`: Search TIDAL for tracks, albums, and artists by name
- `get_favorite_tracks`: Retrieve your favorite tracks from TIDAL
- `recommend_tracks`: Get personalized music recommendations
- `create_tidal_playlist`: Create a new playlist in your TIDAL account
- `add_tracks_to_playlist`: Add tracks to an existing playlist
- `get_user_playlists`: List all your playlists on TIDAL
- `get_playlist_tracks`: Retrieve tracks from a playlist (supports pagination with offset/limit for large playlists)
- `delete_tidal_playlist`: Delete a playlist from your TIDAL account

**Batch Tools** (optimized for large operations):
- `batch_search_tidal`: Search for multiple songs in a single request (up to 100 queries). 10-50x faster than individual searches.
- `create_playlist_from_songs`: Create a playlist from a list of song names/descriptions. Automatically searches for each song and adds the best matches.

**Download Tools** (requires tidal-dl-ng):
- `download_track`: Download a single track by ID
- `download_album`: Download an entire album by ID
- `download_playlist`: Download all tracks from a playlist
- `download_favorites`: Download all favorites (tracks, albums, artists, or videos)

## Troubleshooting

If the MCP server hangs when Claude Desktop tries to call tools:

1. **Delete any local Python environment artifacts**:
   ```bash
   # Remove these if they exist in the project directory
   rm -rf .venv
   rm -rf tidal_mcp.egg-info
   rm -f uv.lock

   # Clear Python cache
   find . -type d -name __pycache__ -exec rm -rf {} +
   ```

2. **Check for port conflicts** (default port is 5050):
   ```bash
   # Windows
   netstat -ano | findstr ":5050"

   # Kill any conflicting processes
   taskkill /PID <pid> /F
   ```

3. **Restart Claude Desktop** after making changes

4. **Check logs** at:
   - Windows: `%APPDATA%\Claude\logs\mcp-server-tidal.log`
   - macOS/Linux: `~/.claude/logs/mcp-server-tidal.log`

## License

[MIT License](LICENSE)

## Acknowledgements

- [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) - Original TIDAL MCP implementation
- [tidal-dl-ng](https://github.com/exislow/tidal-dl-ng) by exislow - TIDAL download functionality
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk)
- [TIDAL Python API](https://github.com/tamland/python-tidal)