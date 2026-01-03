from mcp.server.fastmcp import FastMCP
import requests
from requests.adapters import HTTPAdapter
import atexit
import sys

from typing import Optional, List

from utils import start_flask_app, shutdown_flask_app, FLASK_APP_URL, FLASK_PORT

# Timeout for Flask backend requests (seconds)
# This prevents tools from hanging indefinitely if Flask is unresponsive
REQUEST_TIMEOUT = 15

# HTTP session with connection pooling for efficient communication with Flask backend
# Reuses TCP connections across requests, significantly reducing overhead for batch operations
http_session = requests.Session()
http_session.mount('http://', HTTPAdapter(pool_connections=10, pool_maxsize=10))

# Extended timeout for operations that may take longer (fetching many playlists, etc.)
EXTENDED_TIMEOUT = 60

# Print the port being used for debugging (to stderr per MCP protocol)
print(f"TIDAL MCP starting on port {FLASK_PORT}", file=sys.stderr, flush=True)

# Create an MCP server
mcp = FastMCP("TIDAL MCP")

# Start the Flask app when this script is loaded
print("MCP server module is being loaded. Starting Flask app...", file=sys.stderr, flush=True)
start_flask_app()

# Register the shutdown function to be called when the MCP server exits
atexit.register(shutdown_flask_app)

@mcp.tool()
def tidal_login() -> dict:
    """
    Authenticate with TIDAL through browser login flow.
    This will open a browser window for the user to log in to their TIDAL account.

    Returns:
        A dictionary containing authentication status and user information if successful
    """
    try:
        # Call your Flask endpoint for TIDAL authentication
        # Use longer timeout (5 min) since user needs to complete OAuth in browser
        response = http_session.get(f"{FLASK_APP_URL}/api/auth/login", timeout=300)

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Authentication failed: {error_data.get('message', 'Unknown error')}"
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Login timed out after 5 minutes. Please try again and complete the browser login promptly."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to TIDAL authentication service: {str(e)}"
        }

@mcp.tool()
def get_favorite_tracks(limit: int = 20) -> dict:
    """
    Retrieves tracks from the user's TIDAL account favorites.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "What are my favorite tracks?"
    - "Show me my TIDAL favorites"
    - "What music do I have saved?"
    - "Get my favorite songs"
    - Any request to view their saved/favorite tracks

    This function retrieves the user's favorite tracks from TIDAL.

    Args:
        limit: Maximum number of tracks to retrieve (default: 20, note it should be large enough by default unless specified otherwise).

    Returns:
        A dictionary containing track information including track ID, title, artist, album, and duration.
        Returns an error message if not authenticated or if retrieval fails.
    """
    try:
        # Call Flask endpoint to retrieve tracks - auth is handled by Flask
        response = http_session.get(f"{FLASK_APP_URL}/api/tracks", params={"limit": limit}, timeout=REQUEST_TIMEOUT)

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            return {
                "status": "error",
                "message": "Not authenticated with TIDAL. Please login first using tidal_login()."
            }
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to retrieve tracks: {error_data.get('error', 'Unknown error')}"
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {REQUEST_TIMEOUT}s. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to TIDAL tracks service: {str(e)}"
        }


def _check_auth_error(response) -> dict:
    """Helper to check for auth errors in response. Returns error dict if 401, None otherwise."""
    if response.status_code == 401:
        return {
            "status": "error",
            "message": "Not authenticated with TIDAL. Please login first using tidal_login()."
        }
    return None


def _safe_json(response, default=None):
    """Safely parse JSON from response, returning default if parsing fails."""
    try:
        return response.json()
    except Exception:
        return default if default is not None else {}


@mcp.tool()
def search_tidal(query: str, search_type: str = "all", limit: int = 50) -> dict:
    """
    Search TIDAL's catalog for tracks, albums, artists, and playlists.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Search for [song/album/artist name]"
    - "Find [song name] on TIDAL"
    - "Look up [artist name]"
    - "Search TIDAL for [query]"
    - "Find albums by [artist]"
    - Any request to search or find music in TIDAL's catalog

    When processing the results of this tool:
    1. Present the top_hit first if available - this is TIDAL's most relevant result
    2. Group results by type (tracks, albums, artists, playlists)
    3. Include the TIDAL URL for each result so users can easily access them
    4. For tracks, include artist and album information
    5. For albums, include artist and track count
    6. Format results in a clear, readable manner

    Args:
        query: Search query (e.g., "Bohemian Rhapsody", "Radiohead", "Dark Side of the Moon")
        search_type: Type of content to search for:
                    - "track" - Search only for tracks/songs
                    - "album" - Search only for albums
                    - "artist" - Search only for artists
                    - "playlist" - Search only for playlists
                    - "all" (default) - Search all content types
        limit: Maximum number of results per type (default: 50, max: 300)

    Returns:
        Dictionary with search results organized by type (tracks, albums, artists, playlists)
        and an optional top_hit for the most relevant result
    """
    # Validate search_type
    valid_types = ["track", "album", "artist", "playlist", "all"]
    if search_type.lower() not in valid_types:
        return {
            "status": "error",
            "message": f"Invalid search_type '{search_type}'. Must be one of: {', '.join(valid_types)}"
        }

    # Validate query
    if not query or not query.strip():
        return {
            "status": "error",
            "message": "Search query cannot be empty."
        }

    try:
        response = http_session.get(
            f"{FLASK_APP_URL}/api/search",
            params={"q": query.strip(), "type": search_type.lower(), "limit": limit},
            timeout=REQUEST_TIMEOUT
        )

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        if response.status_code == 200:
            result = response.json()
            return {
                "status": "success",
                "query": query,
                "search_type": search_type,
                **result
            }
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": error_data.get("error", "Search failed")
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Search timed out after {REQUEST_TIMEOUT}s. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to search TIDAL: {str(e)}"
        }


@mcp.tool()
def batch_search_tidal(queries: List[dict], limit_per_query: int = 5) -> dict:
    """
    Search TIDAL for multiple tracks/albums/artists in a single request.
    This is MUCH MORE EFFICIENT than calling search_tidal multiple times.

    USE THIS TOOL WHEN:
    - You need to search for multiple songs to create a playlist
    - You have a list of song names to look up
    - You're building a collection of tracks based on a user's description
    - The user provides a list of songs they want to find

    This tool processes all searches concurrently, making it 10-50x faster than
    calling search_tidal repeatedly for each song.

    When processing the results:
    1. Check each result for the 'tracks' array with matching songs
    2. Use the first track in each result as the best match
    3. Some queries may have 'error' instead of results - handle gracefully
    4. Collect track IDs for playlist creation

    Args:
        queries: List of search queries. Each item can be:
                 - A string: "Bohemian Rhapsody Queen" (searches for tracks)
                 - A dict with 'query' and optional 'type':
                   {"query": "Bohemian Rhapsody", "type": "track"}
                 Valid types: "track", "album", "artist", "playlist", "all"
                 Default type is "track" if not specified.
                 Maximum 100 queries per request.
        limit_per_query: Maximum results per query (default: 5, max: 20)
                        Keep this low (1-5) for faster responses when you only need the best match.

    Returns:
        Dictionary with 'results' array containing search results for each query.
        Each result includes the original query and matching tracks/albums/etc.

    Example:
        batch_search_tidal([
            {"query": "Bohemian Rhapsody Queen", "type": "track"},
            {"query": "Yesterday Beatles", "type": "track"},
            "Stairway to Heaven"  # String queries default to track type
        ], limit_per_query=1)
    """
    try:
        if not queries or not isinstance(queries, list):
            return {"status": "error", "message": "queries must be a non-empty list"}

        if len(queries) > 100:
            return {"status": "error", "message": "Maximum 100 queries per batch request"}

        # Normalize queries to consistent format
        normalized_queries = []
        for q in queries:
            if isinstance(q, str):
                normalized_queries.append({"query": q, "type": "track"})
            elif isinstance(q, dict) and q.get("query"):
                normalized_queries.append({
                    "query": q["query"],
                    "type": q.get("type", "track")
                })

        if not normalized_queries:
            return {"status": "error", "message": "No valid queries provided"}

        response = http_session.post(
            f"{FLASK_APP_URL}/api/search/batch",
            json={"queries": normalized_queries, "limit_per_query": min(max(1, limit_per_query), 20)},
            timeout=EXTENDED_TIMEOUT  # Use extended timeout for batch
        )

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        if response.status_code == 200:
            data = _safe_json(response)
            if not data:
                return {"status": "error", "message": "Empty response from batch search - Flask may have crashed"}
            return {"status": "success", **data}
        else:
            error_data = _safe_json(response)
            return {"status": "error", "message": error_data.get("error", f"Batch search failed (HTTP {response.status_code})")}

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Batch search timed out. Try with fewer queries."}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Cannot connect to TIDAL backend service."}
    except Exception as e:
        return {"status": "error", "message": f"Batch search failed: {str(e)}"}


@mcp.tool()
def create_playlist_from_songs(
    title: str,
    song_descriptions: List[str],
    description: str = ""
) -> dict:
    """
    Creates a TIDAL playlist by searching for songs and adding the best matches.
    This is the RECOMMENDED way to create a playlist when you have song names/descriptions.

    USE THIS TOOL WHEN:
    - A user provides a list of song names to add to a playlist
    - You need to create a playlist from song descriptions (not track IDs)
    - You want to build a playlist based on user-provided song names

    This tool handles the entire workflow efficiently:
    1. Batch search for all songs concurrently
    2. Collect the best matching track IDs
    3. Create the playlist with all found tracks

    This is MUCH faster than searching for songs one-by-one and then creating a playlist.

    Args:
        title: Name for the new playlist
        song_descriptions: List of song descriptions to search for.
                          Include artist name for better matching.
                          Examples: ["Bohemian Rhapsody by Queen", "Yesterday Beatles",
                                    "Stairway to Heaven Led Zeppelin"]
                          Maximum 100 songs per request.
        description: Optional playlist description

    Returns:
        Dictionary with:
        - playlist: Created playlist details including URL
        - matched_songs: List of songs that were found with their track info
        - unmatched_songs: List of songs that couldn't be found
        - match_rate: e.g., "45/50" showing how many songs were matched

    Example:
        create_playlist_from_songs(
            title="My 80s Favorites",
            song_descriptions=[
                "Take On Me a-ha",
                "Livin' on a Prayer Bon Jovi",
                "Sweet Child O' Mine Guns N' Roses"
            ],
            description="Classic 80s hits"
        )
    """
    # Validate inputs
    if not title:
        return {"status": "error", "message": "Playlist title is required"}

    if not song_descriptions or not isinstance(song_descriptions, list):
        return {"status": "error", "message": "song_descriptions must be a non-empty list"}

    if len(song_descriptions) > 100:
        return {"status": "error", "message": "Maximum 100 songs per playlist creation"}

    try:
        # Step 1: Batch search for all songs
        queries = [{"query": s, "type": "track"} for s in song_descriptions if s]
        search_response = http_session.post(
            f"{FLASK_APP_URL}/api/search/batch",
            json={"queries": queries, "limit_per_query": 1},  # Only need best match
            timeout=EXTENDED_TIMEOUT
        )

        auth_error = _check_auth_error(search_response)
        if auth_error:
            return auth_error

        if search_response.status_code != 200:
            error_data = _safe_json(search_response)
            error_msg = error_data.get('error', f"HTTP {search_response.status_code}")
            return {"status": "error", "message": f"Failed to search for songs: {error_msg}"}

        search_data = _safe_json(search_response)
        if not search_data:
            return {"status": "error", "message": "Empty response from search - Flask may have crashed"}

        # Step 2: Collect track IDs and track matched/unmatched songs
        track_ids = []
        matched_songs = []
        unmatched_songs = []

        for result in search_data.get("results", []):
            query = result.get("query", "")
            tracks = result.get("tracks", [])

            if tracks and len(tracks) > 0:
                track = tracks[0]
                track_id = track.get("id")
                if track_id:
                    track_ids.append(track_id)
                    matched_songs.append({
                        "query": query,
                        "matched_track": track.get("title", "Unknown"),
                        "matched_artist": track.get("artist", "Unknown"),
                        "track_id": track_id,
                        "url": track.get("url", "")
                    })
            else:
                unmatched_songs.append(query)

        if not track_ids:
            return {
                "status": "error",
                "message": "Could not find any matching tracks on TIDAL",
                "unmatched_songs": unmatched_songs
            }

        # Step 3: Create the playlist with found tracks
        create_response = http_session.post(
            f"{FLASK_APP_URL}/api/playlists",
            json={"title": title, "description": description, "track_ids": track_ids},
            timeout=30
        )

        auth_error = _check_auth_error(create_response)
        if auth_error:
            return auth_error

        if create_response.status_code != 200:
            error_data = _safe_json(create_response)
            error_msg = error_data.get('error', f"HTTP {create_response.status_code}")
            return {"status": "error", "message": f"Failed to create playlist: {error_msg}"}

        playlist_data = _safe_json(create_response)
        if not playlist_data:
            return {"status": "error", "message": "Empty response from playlist creation - Flask may have crashed"}
        playlist_info = playlist_data.get("playlist", {})

        return {
            "status": "success",
            "message": f"Created playlist '{title}' with {len(track_ids)} tracks",
            "playlist": {
                **playlist_info,
                "playlist_url": f"https://tidal.com/playlist/{playlist_info.get('id')}"
            },
            "matched_songs": matched_songs,
            "unmatched_songs": unmatched_songs,
            "match_rate": f"{len(matched_songs)}/{len(song_descriptions)}"
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. Try with fewer songs."}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Cannot connect to TIDAL backend service."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to create playlist: {str(e)}"}


def _get_tidal_recommendations(track_ids: list = None, limit_per_track: int = 20, filter_criteria: str = None) -> dict:
    """
    [INTERNAL USE] Gets raw recommendation data from TIDAL API.
    This is a lower-level function primarily used by higher-level recommendation functions.
    For end-user recommendations, use recommend_tracks instead.

    Args:
        track_ids: List of TIDAL track IDs to use as seeds for recommendations.
        limit_per_track: Maximum number of recommendations to get per track (default: 20)
        filter_criteria: Optional string describing criteria to filter recommendations
                         (e.g., "relaxing", "new releases", "upbeat")

    Returns:
        A dictionary containing recommended tracks based on seed tracks and filtering criteria.
    """
    try:
        # Validate track_ids
        if not track_ids or not isinstance(track_ids, list) or len(track_ids) == 0:
            return {
                "status": "error",
                "message": "No track IDs provided for recommendations."
            }

        # Call the batch recommendations endpoint
        payload = {
            "track_ids": track_ids,
            "limit_per_track": limit_per_track,
            "remove_duplicates": True
        }

        response = http_session.post(f"{FLASK_APP_URL}/api/recommendations/batch", json=payload, timeout=60)

        if response.status_code != 200:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to get recommendations: {error_data.get('error', 'Unknown error')}"
            }

        recommendations = response.json().get("recommendations", [])

        # If filter criteria is provided, include it in the response for LLM processing
        result = {
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }

        if filter_criteria:
            result["filter_criteria"] = filter_criteria

        return result

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Recommendations request timed out. Try with fewer seed tracks."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get recommendations: {str(e)}"
        }

@mcp.tool()
def recommend_tracks(track_ids: Optional[List[str]] = None, filter_criteria: Optional[str] = None, limit_per_track: int = 20, limit_from_favorite: int = 20) -> dict:
    """
    Recommends music tracks based on specified track IDs or can use the user's TIDAL favorites if no IDs are provided.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - Music recommendations
    - Track suggestions
    - Music similar to their TIDAL favorites or specific tracks
    - "What should I listen to?"
    - Any request to recommend songs/tracks/music based on their TIDAL history or specific tracks

    This function gets recommendations based on provided track IDs or retrieves the user's
    favorite tracks as seeds if no IDs are specified.

    When processing the results of this tool:
    1. Analyze the seed tracks to understand the music taste or direction
    2. Review the recommended tracks from TIDAL
    3. IMPORTANT: Do NOT include any tracks from the seed tracks in your recommendations
    4. Ensure there are NO DUPLICATES in your recommended tracks list
    5. Select and rank the most appropriate tracks based on the seed tracks and filter criteria
    6. Group recommendations by similar styles, artists, or moods with descriptive headings
    7. For each recommended track, provide:
       - The track name, artist, album
       - Always include the track's URL to make it easy for users to listen to the track
       - A brief explanation of why this track might appeal to the user based on the seed tracks
       - If applicable, how this track matches their specific filter criteria
    8. Format your response as a nicely presented list of recommendations with helpful context (remember to include the track's URL!)
    9. Begin with a brief introduction explaining your selection strategy
    10. Lastly, unless specified otherwise, you should recommend MINIMUM 20 tracks (or more if possible) to give the user a good variety to choose from.

    [IMPORTANT NOTE] If you're not familiar with any artists or tracks mentioned, you should use internet search capabilities if available to provide more accurate information.

    Args:
        track_ids: Optional list of TIDAL track IDs to use as seeds for recommendations.
                  If not provided, will use the user's favorite tracks.
        filter_criteria: Specific preferences for filtering recommendations (e.g., "relaxing music,"
                         "recent releases," "upbeat," "jazz influences")
        limit_per_track: Maximum number of recommendations to get per track (NOTE: default: 20, unless specified otherwise, we'd like to keep the default large enough to have enough candidates to work with)
        limit_from_favorite: Maximum number of favorite tracks to use as seeds (NOTE: default: 20, unless specified otherwise, we'd like to keep the default large enough to have enough candidates to work with)

    Returns:
        A dictionary containing both the seed tracks and recommended tracks
    """
    # Initialize variables to store our seed tracks and their info
    seed_track_ids = []
    seed_tracks_info = []

    # If track_ids are provided, use them directly
    if track_ids and isinstance(track_ids, list) and len(track_ids) > 0:
        seed_track_ids = track_ids
        # Note: We don't have detailed info about these tracks, just IDs
        # This is fine as the recommendation API only needs IDs
    else:
        # If no track_ids provided, get the user's favorite tracks
        tracks_response = get_favorite_tracks(limit=limit_from_favorite)

        # Check if we successfully retrieved tracks
        if "status" in tracks_response and tracks_response["status"] == "error":
            return {
                "status": "error",
                "message": f"Unable to get favorite tracks for recommendations: {tracks_response['message']}"
            }

        # Extract the track data
        favorite_tracks = tracks_response.get("tracks", [])

        if not favorite_tracks:
            return {
                "status": "error",
                "message": "I couldn't find any favorite tracks in your TIDAL account to use as seeds for recommendations."
            }

        # Use these as our seed tracks
        seed_track_ids = [track["id"] for track in favorite_tracks]
        seed_tracks_info = favorite_tracks

    # Get recommendations based on the seed tracks
    recommendations_response = _get_tidal_recommendations(
        track_ids=seed_track_ids,
        limit_per_track=limit_per_track,
        filter_criteria=filter_criteria
    )

    # Check if we successfully retrieved recommendations
    if "status" in recommendations_response and recommendations_response["status"] == "error":
        return {
            "status": "error",
            "message": f"Unable to get recommendations: {recommendations_response['message']}"
        }

    # Get the recommendations
    recommendations = recommendations_response.get("recommendations", [])

    if not recommendations:
        return {
            "status": "error",
            "message": "I couldn't find any recommendations based on the provided tracks. Please try again with different tracks or adjust your filtering criteria."
        }

    # Return the structured data to process
    return {
        "status": "success",
        "seed_tracks": seed_tracks_info,  # This might be empty if direct track_ids were provided
        "seed_track_ids": seed_track_ids,
        "recommendations": recommendations,
        "filter_criteria": filter_criteria,
        "seed_count": len(seed_track_ids),
    }


@mcp.tool()
def create_tidal_playlist(title: str, track_ids: list, description: str = "") -> dict:
    """
    Creates a new TIDAL playlist with the specified tracks.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Create a playlist with these songs"
    - "Make a TIDAL playlist"
    - "Save these tracks to a playlist"
    - "Create a collection of songs"
    - Any request to create a new playlist in their TIDAL account

    This function creates a new playlist in the user's TIDAL account and adds the specified tracks to it.
    The user must be authenticated with TIDAL first.

    NAMING CONVENTION GUIDANCE:
    When suggesting or creating a playlist, first check the user's existing playlists using get_user_playlists()
    to understand their naming preferences. Some patterns to look for:
    - Do they use emoji in playlist names?
    - Do they use all caps, title case, or lowercase?
    - Do they include dates or seasons in names?
    - Do they name by mood, genre, activity, or artist?
    - Do they use specific prefixes or formatting (e.g., "Mix: Summer Vibes" or "[Workout] High Energy")

    Try to match their style when suggesting new playlist names. If they have no playlists yet or you
    can't determine a pattern, use a clear, descriptive name based on the tracks' common themes.

    When processing the results of this tool:
    1. Confirm the playlist was created successfully
    2. Provide the playlist title, number of tracks added, and URL
    3. Always include the direct TIDAL URL (https://tidal.com/playlist/{playlist_id})
    4. Suggest that the user can now access this playlist in their TIDAL account

    Args:
        title: The name of the playlist to create
        track_ids: List of TIDAL track IDs to add to the playlist
        description: Optional description for the playlist (default: "")

    Returns:
        A dictionary containing the status of the playlist creation and details about the created playlist
    """
    # Validate inputs
    if not title:
        return {
            "status": "error",
            "message": "Playlist title cannot be empty."
        }

    if not track_ids or not isinstance(track_ids, list) or len(track_ids) == 0:
        return {
            "status": "error",
            "message": "You must provide at least one track ID to add to the playlist."
        }

    try:
        # Create the playlist through the Flask API
        payload = {
            "title": title,
            "description": description,
            "track_ids": track_ids
        }

        response = http_session.post(f"{FLASK_APP_URL}/api/playlists", json=payload, timeout=30)

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        # Check response
        if response.status_code != 200:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to create playlist: {error_data.get('error', 'Unknown error')}"
            }

        # Parse the response
        result = response.json()
        playlist_data = result.get("playlist", {})

        # Get the playlist ID
        playlist_id = playlist_data.get("id")

        # Format the TIDAL URL
        playlist_url = f"https://tidal.com/playlist/{playlist_id}" if playlist_id else None
        playlist_data["playlist_url"] = playlist_url

        return {
            "status": "success",
            "message": f"Successfully created playlist '{title}' with {len(track_ids)} tracks",
            "playlist": playlist_data
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Playlist creation timed out. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create playlist: {str(e)}"
        }


@mcp.tool()
def add_tracks_to_playlist(playlist_id: str, track_ids: list, allow_duplicates: bool = False) -> dict:
    """
    Adds tracks to an existing TIDAL playlist.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Add this song to my playlist"
    - "Put these tracks in my [playlist name] playlist"
    - "Add this to my favorites playlist"
    - "Include this track in my workout playlist"
    - Any request to add songs/tracks to an existing playlist

    This function adds one or more tracks to a playlist that already exists in the user's TIDAL account.
    The playlist_id must be provided, which can be obtained from the get_user_playlists() function.

    When processing the results of this tool:
    1. Confirm how many tracks were successfully added
    2. If allow_duplicates is False and some tracks were already in the playlist, they won't be added again
    3. Mention the playlist name and provide a link to it

    Args:
        playlist_id: The TIDAL ID of the playlist to add tracks to (required)
        track_ids: List of TIDAL track IDs to add to the playlist (required)
        allow_duplicates: If False (default), tracks already in the playlist won't be added again

    Returns:
        A dictionary containing the status and number of tracks added
    """
    # Validate inputs
    if not playlist_id:
        return {
            "status": "error",
            "message": "Playlist ID is required. You can get playlist IDs by using the get_user_playlists() function."
        }

    if not track_ids or not isinstance(track_ids, list) or len(track_ids) == 0:
        return {
            "status": "error",
            "message": "You must provide at least one track ID to add to the playlist."
        }

    try:
        # Add tracks through the Flask API
        payload = {
            "track_ids": track_ids,
            "allow_duplicates": allow_duplicates
        }

        response = http_session.post(
            f"{FLASK_APP_URL}/api/playlists/{playlist_id}/tracks",
            json=payload,
            timeout=30
        )

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        # Check response
        if response.status_code == 404:
            return {
                "status": "error",
                "message": f"Playlist with ID {playlist_id} not found. Please check the playlist ID and try again."
            }

        if response.status_code != 200:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to add tracks to playlist: {error_data.get('error', 'Unknown error')}"
            }

        # Parse the response
        result = response.json()

        return {
            "status": "success",
            "message": result.get("message", f"Added tracks to playlist"),
            "playlist_id": playlist_id,
            "playlist_url": f"https://tidal.com/playlist/{playlist_id}",
            "tracks_added": result.get("tracks_added", 0)
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timed out. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to add tracks to playlist: {str(e)}"
        }


@mcp.tool()
def get_user_playlists() -> dict:
    """
    Fetches the user's playlists from their TIDAL account.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Show me my playlists"
    - "List my TIDAL playlists"
    - "What playlists do I have?"
    - "Get my music collections"
    - Any request to view or list their TIDAL playlists

    This function retrieves the user's playlists from TIDAL and returns them sorted
    by last updated date (most recent first).

    When processing the results of this tool:
    1. Present the playlists in a clear, organized format
    2. Include key information like title, track count, and the TIDAL URL for each playlist
    3. Mention when each playlist was last updated if available
    4. If the user has many playlists, focus on the most recently updated ones unless specified otherwise

    Returns:
        A dictionary containing the user's playlists sorted by last updated date
    """
    try:
        # Call the Flask endpoint to retrieve playlists
        # Use extended timeout since users may have many playlists (200+)
        response = http_session.get(f"{FLASK_APP_URL}/api/playlists", timeout=EXTENDED_TIMEOUT)

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "playlists": data.get("playlists", []),
                "playlist_count": len(data.get("playlists", []))
            }
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to retrieve playlists: {error_data.get('error', 'Unknown error')}"
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {EXTENDED_TIMEOUT}s. You may have many playlists - try again."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to TIDAL playlists service: {str(e)}"
        }


@mcp.tool()
def get_playlist_tracks(playlist_id: str, limit: int = 100, offset: int = 0) -> dict:
    """
    Retrieves tracks from a specified TIDAL playlist with pagination support.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Show me the songs in my playlist"
    - "What tracks are in my [playlist name] playlist?"
    - "List the songs from my playlist"
    - "Get tracks from my playlist"
    - "View contents of my TIDAL playlist"
    - Any request to see what songs/tracks are in a specific playlist

    This function retrieves tracks from a specific playlist in the user's TIDAL account.
    The playlist_id must be provided, which can be obtained from the get_user_playlists() function.

    PAGINATION: For large playlists, use the offset parameter to get additional tracks.
    The response includes 'total_available' showing the total tracks in the playlist.
    If total_available > track_count, call again with offset incremented by the limit
    to get the next batch (e.g., first call offset=0, second call offset=100, etc.)

    When processing the results of this tool:
    1. Present the playlist information (title, description, track count) as context
    2. List the tracks in a clear, organized format with track name, artist, and album
    3. Include track durations where available
    4. Check total_available vs track_count to know if there are more tracks
    5. If there are many tracks, focus on highlighting interesting patterns or variety

    Args:
        playlist_id: The TIDAL ID of the playlist to retrieve (required)
        limit: Maximum number of tracks to retrieve per request (default: 100, max: 500)
        offset: Starting index for pagination (default: 0). Use to get additional tracks.

    Returns:
        A dictionary containing tracks, track_count (returned), total_available (in playlist), offset, and limit
    """
    # Validate playlist_id
    if not playlist_id:
        return {
            "status": "error",
            "message": "A playlist ID is required. You can get playlist IDs by using the get_user_playlists() function."
        }

    try:
        # Call the Flask endpoint to retrieve tracks from the playlist
        response = http_session.get(
            f"{FLASK_APP_URL}/api/playlists/{playlist_id}/tracks",
            params={"limit": limit, "offset": offset},
            timeout=REQUEST_TIMEOUT
        )

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "tracks": data.get("tracks", []),
                "track_count": data.get("total_tracks", 0),
                "total_available": data.get("total_available", 0),
                "offset": data.get("offset", 0),
                "limit": data.get("limit", limit)
            }
        elif response.status_code == 404:
            return {
                "status": "error",
                "message": f"Playlist with ID {playlist_id} not found. Please check the playlist ID and try again."
            }
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to retrieve playlist tracks: {error_data.get('error', 'Unknown error')}"
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {REQUEST_TIMEOUT}s. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to TIDAL playlist service: {str(e)}"
        }


@mcp.tool()
def delete_tidal_playlist(playlist_id: str) -> dict:
    """
    Deletes a TIDAL playlist by its ID.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Delete my playlist"
    - "Remove a playlist from my TIDAL account"
    - "Get rid of this playlist"
    - "Delete the playlist with ID X"
    - Any request to delete or remove a TIDAL playlist

    This function deletes a specific playlist from the user's TIDAL account.
    The user must be authenticated with TIDAL first.

    When processing the results of this tool:
    1. Confirm the playlist was deleted successfully
    2. Provide a clear message about the deletion

    Args:
        playlist_id: The TIDAL ID of the playlist to delete (required)

    Returns:
        A dictionary containing the status of the playlist deletion
    """
    # Validate playlist_id
    if not playlist_id:
        return {
            "status": "error",
            "message": "A playlist ID is required. You can get playlist IDs by using the get_user_playlists() function."
        }

    try:
        # Call the Flask endpoint to delete the playlist
        response = http_session.delete(f"{FLASK_APP_URL}/api/playlists/{playlist_id}", timeout=REQUEST_TIMEOUT)

        auth_error = _check_auth_error(response)
        if auth_error:
            return auth_error

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {
                "status": "error",
                "message": f"Playlist with ID {playlist_id} not found. Please check the playlist ID and try again."
            }
        else:
            error_data = response.json()
            return {
                "status": "error",
                "message": f"Failed to delete playlist: {error_data.get('error', 'Unknown error')}"
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {REQUEST_TIMEOUT}s. The TIDAL backend may be unresponsive."
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Cannot connect to TIDAL backend service. The MCP server may need to be restarted."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to TIDAL playlist service: {str(e)}"
        }


# =============================================================================
# Download Tools (using tidal-dl-ng CLI)
# These tools require tidal-dl-ng to be installed and authenticated separately.
# =============================================================================

@mcp.tool()
def download_track(track_id: str) -> dict:
    """
    Downloads a TIDAL track to local storage using tidal-dl-ng.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Download this track"
    - "Save this song to my computer"
    - "Download track ID X"
    - "I want to download [song name]" (after identifying the track ID)
    - Any request to download a single track from TIDAL

    IMPORTANT PREREQUISITES:
    1. tidal-dl-ng must be installed: pip install tidal-dl-ng
    2. User must have authenticated tidal-dl-ng: run 'tdn login' in terminal
    3. tidal-dl-ng authentication is SEPARATE from TIDAL MCP authentication

    When processing the results of this tool:
    1. Confirm the download was successful or explain any errors
    2. If tidal-dl-ng is not installed, guide user to install it
    3. If authentication failed, guide user to run 'tdn login' in terminal
    4. The file will be saved to tidal-dl-ng's configured download location

    Args:
        track_id: The TIDAL track ID to download (numeric string)

    Returns:
        A dictionary containing download status and any output messages
    """
    try:
        # Check if tdn is installed first
        status_check = http_session.get(f"{FLASK_APP_URL}/api/download/status", timeout=REQUEST_TIMEOUT)
        status_data = status_check.json()

        if not status_data.get("installed", False):
            return {
                "status": "error",
                "message": "tidal-dl-ng is not installed. Please install it with: pip install tidal-dl-ng"
            }

        # Validate track_id
        if not track_id:
            return {
                "status": "error",
                "message": "Track ID is required."
            }

        # Attempt download
        response = http_session.post(
            f"{FLASK_APP_URL}/api/download/track",
            json={"track_id": track_id},
            timeout=320
        )

        result = response.json()

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"Successfully downloaded track {track_id}",
                "url": result.get("url", ""),
                "details": result.get("output", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", result.get("error", "Download failed"))
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Download request timed out. The track may still be downloading in the background."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to download track: {str(e)}"
        }


@mcp.tool()
def download_album(album_id: str) -> dict:
    """
    Downloads a TIDAL album to local storage using tidal-dl-ng.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Download this album"
    - "Save this album to my computer"
    - "Download album ID X"
    - "I want to download [album name]" (after identifying the album ID)
    - Any request to download a complete album from TIDAL

    IMPORTANT PREREQUISITES:
    1. tidal-dl-ng must be installed: pip install tidal-dl-ng
    2. User must have authenticated tidal-dl-ng: run 'tdn login' in terminal
    3. tidal-dl-ng authentication is SEPARATE from TIDAL MCP authentication

    When processing the results of this tool:
    1. Confirm the download was successful or explain any errors
    2. Note that albums may take several minutes to download
    3. If tidal-dl-ng is not installed, guide user to install it
    4. If authentication failed, guide user to run 'tdn login' in terminal
    5. The files will be saved to tidal-dl-ng's configured download location

    Args:
        album_id: The TIDAL album ID to download (numeric string)

    Returns:
        A dictionary containing download status and any output messages
    """
    try:
        # Check if tdn is installed first
        status_check = http_session.get(f"{FLASK_APP_URL}/api/download/status", timeout=REQUEST_TIMEOUT)
        status_data = status_check.json()

        if not status_data.get("installed", False):
            return {
                "status": "error",
                "message": "tidal-dl-ng is not installed. Please install it with: pip install tidal-dl-ng"
            }

        # Validate album_id
        if not album_id:
            return {
                "status": "error",
                "message": "Album ID is required."
            }

        # Attempt download (longer timeout for albums)
        response = http_session.post(
            f"{FLASK_APP_URL}/api/download/album",
            json={"album_id": album_id},
            timeout=620
        )

        result = response.json()

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"Successfully downloaded album {album_id}",
                "url": result.get("url", ""),
                "details": result.get("output", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", result.get("error", "Download failed"))
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Download request timed out. The album may still be downloading in the background."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to download album: {str(e)}"
        }


@mcp.tool()
def download_playlist(playlist_id: str) -> dict:
    """
    Downloads a TIDAL playlist to local storage using tidal-dl-ng.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Download this playlist"
    - "Save this playlist to my computer"
    - "Download playlist ID X"
    - "I want to download [playlist name]" (after identifying the playlist ID)
    - Any request to download a complete playlist from TIDAL

    IMPORTANT PREREQUISITES:
    1. tidal-dl-ng must be installed: pip install tidal-dl-ng
    2. User must have authenticated tidal-dl-ng: run 'tdn login' in terminal
    3. tidal-dl-ng authentication is SEPARATE from TIDAL MCP authentication

    When processing the results of this tool:
    1. Confirm the download was successful or explain any errors
    2. Note that playlists may take a long time to download depending on size
    3. If tidal-dl-ng is not installed, guide user to install it
    4. If authentication failed, guide user to run 'tdn login' in terminal
    5. The files will be saved to tidal-dl-ng's configured download location

    You can get playlist IDs from the get_user_playlists() function.

    Args:
        playlist_id: The TIDAL playlist ID/UUID to download

    Returns:
        A dictionary containing download status and any output messages
    """
    try:
        # Check if tdn is installed first
        status_check = http_session.get(f"{FLASK_APP_URL}/api/download/status", timeout=REQUEST_TIMEOUT)
        status_data = status_check.json()

        if not status_data.get("installed", False):
            return {
                "status": "error",
                "message": "tidal-dl-ng is not installed. Please install it with: pip install tidal-dl-ng"
            }

        # Validate playlist_id
        if not playlist_id:
            return {
                "status": "error",
                "message": "Playlist ID is required. You can get playlist IDs using get_user_playlists()."
            }

        # Attempt download (longest timeout for playlists)
        response = http_session.post(
            f"{FLASK_APP_URL}/api/download/playlist",
            json={"playlist_id": playlist_id},
            timeout=1220
        )

        result = response.json()

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"Successfully downloaded playlist {playlist_id}",
                "url": result.get("url", ""),
                "details": result.get("output", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", result.get("error", "Download failed"))
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Download request timed out. The playlist may still be downloading in the background."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to download playlist: {str(e)}"
        }


@mcp.tool()
def download_favorites(favorite_type: str = "tracks") -> dict:
    """
    Downloads all favorites of a specific type from TIDAL using tidal-dl-ng.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Download all my favorite tracks"
    - "Download my saved albums"
    - "Save all my favorites to my computer"
    - "Download my favorite artists' music"
    - Any request to download their saved/favorite content from TIDAL

    IMPORTANT PREREQUISITES:
    1. tidal-dl-ng must be installed: pip install tidal-dl-ng
    2. User must have authenticated tidal-dl-ng: run 'tdn login' in terminal
    3. tidal-dl-ng authentication is SEPARATE from TIDAL MCP authentication

    When processing the results of this tool:
    1. Confirm the download was started/completed or explain any errors
    2. Warn user that downloading all favorites can take a VERY long time
    3. If tidal-dl-ng is not installed, guide user to install it
    4. If authentication failed, guide user to run 'tdn login' in terminal
    5. The files will be saved to tidal-dl-ng's configured download location

    Args:
        favorite_type: Type of favorites to download. One of:
                      - "tracks" (default) - Download all favorite tracks
                      - "albums" - Download all favorite albums
                      - "artists" - Download all content from favorite artists
                      - "videos" - Download all favorite videos

    Returns:
        A dictionary containing download status and any output messages
    """
    try:
        # Validate favorite_type
        valid_types = ["tracks", "albums", "artists", "videos"]
        if favorite_type.lower() not in valid_types:
            return {
                "status": "error",
                "message": f"Invalid favorite type '{favorite_type}'. Must be one of: {', '.join(valid_types)}"
            }

        # Check if tdn is installed first
        status_check = http_session.get(f"{FLASK_APP_URL}/api/download/status", timeout=REQUEST_TIMEOUT)
        status_data = status_check.json()

        if not status_data.get("installed", False):
            return {
                "status": "error",
                "message": "tidal-dl-ng is not installed. Please install it with: pip install tidal-dl-ng"
            }

        # Attempt download (very long timeout for favorites)
        response = http_session.post(
            f"{FLASK_APP_URL}/api/download/favorites",
            json={"type": favorite_type.lower()},
            timeout=1820
        )

        result = response.json()

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"Successfully downloaded favorite {favorite_type}",
                "details": result.get("output", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", result.get("error", "Download failed"))
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Download request timed out. The {favorite_type} may still be downloading in the background."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to download favorites: {str(e)}"
        }
