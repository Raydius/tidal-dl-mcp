import os
import sys
import tempfile
import functools
import time
from threading import Lock

import tidalapi
from tidalapi.types import ItemOrder, OrderDirection
from flask import Flask, request, jsonify
from pathlib import Path

from browser_session import BrowserSession
from utils import format_track_data, format_album_data, format_artist_data, format_playlist_data, bound_limit
from download_utils import (
    check_tdn_installed,
    execute_tdn_download,
    execute_tdn_download_favorites,
    build_tidal_url
)

app = Flask(__name__)
token_path = os.path.join(tempfile.gettempdir(), 'tidal-session-oauth.json')
SESSION_FILE = Path(token_path)

# Session caching to avoid re-validating TIDAL credentials on every request
# This significantly improves performance for batch operations
_cached_session = None
_session_lock = Lock()
_session_last_validated = 0
SESSION_CACHE_TTL = 300  # Re-validate every 5 minutes


def get_or_create_session():
    """
    Get cached TIDAL session or create/validate a new one.
    Thread-safe with TTL-based cache invalidation.

    Returns:
        BrowserSession if valid session exists, None otherwise
    """
    global _cached_session, _session_last_validated

    with _session_lock:
        now = time.time()

        # If session exists and was validated recently, return it
        if _cached_session and (now - _session_last_validated) < SESSION_CACHE_TTL:
            return _cached_session

        # Otherwise, load/validate session
        if not SESSION_FILE.exists():
            _cached_session = None
            return None

        try:
            session = BrowserSession()
            if session.login_session_file_auto(SESSION_FILE):
                _cached_session = session
                _session_last_validated = now
                return session
        except Exception as e:
            print(f"Session validation failed: {e}", file=sys.stderr, flush=True)

        _cached_session = None
        return None


def invalidate_session_cache():
    """Invalidate the cached session (e.g., after logout or auth failure)."""
    global _cached_session, _session_last_validated
    with _session_lock:
        _cached_session = None
        _session_last_validated = 0

def requires_tidal_auth(f):
    """
    Decorator to ensure routes have an authenticated TIDAL session.
    Returns 401 if not authenticated.
    Passes the authenticated session to the decorated function.
    Uses cached session for improved performance.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Use cached session for efficiency
        session = get_or_create_session()

        if not session:
            return jsonify({"error": "Not authenticated"}), 401

        # Add the authenticated session to kwargs
        kwargs['session'] = session
        return f(*args, **kwargs)
    return decorated_function


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to verify Flask backend is running.
    Used by MCP server to verify Flask started successfully.
    """
    return jsonify({"status": "ok"}), 200


@app.route('/api/auth/login', methods=['GET'])
def login():
    """
    Initiates the TIDAL authentication process.
    Automatically opens a browser for the user to login to their TIDAL account.
    """
    # Create our custom session object
    session = BrowserSession()

    def log_message(msg):
        print(f"TIDAL AUTH: {msg}", file=sys.stderr, flush=True)

    # Try to authenticate (will open browser if needed)
    try:
        login_success = session.login_session_file_auto(SESSION_FILE, fn_print=log_message)

        if login_success:
            return jsonify({
                "status": "success",
                "message": "Successfully authenticated with TIDAL",
                "user_id": session.user.id
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Authentication failed"
            }), 401

    except TimeoutError:
        return jsonify({
            "status": "error",
            "message": "Authentication timed out"
        }), 408

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """
    Check if there's an active authenticated session.
    Uses cached session for fast response in batch operations.
    """
    # Use cached session for efficiency
    session = get_or_create_session()

    if session:
        # Get basic user info
        user_info = {
            "id": session.user.id,
            "username": session.user.username if hasattr(session.user, 'username') else "N/A",
        }

        return jsonify({
            "authenticated": True,
            "message": "Valid TIDAL session",
            "user": user_info
        })
    else:
        return jsonify({
            "authenticated": False,
            "message": "No valid session"
        })

@app.route('/api/tracks', methods=['GET'])
@requires_tidal_auth
def get_tracks(session: BrowserSession):
    """
    Get tracks from the user's history.
    """
    try:
        # TODO: Add streaminig history support if TIDAL API allows it
        # Get user favorites or history (for now limiting to user favorites only)
        favorites = session.user.favorites

        # Get limit from query parameter, default to 10 if not specified
        limit = bound_limit(request.args.get('limit', default=10, type=int))

        tracks = favorites.tracks(limit=limit, order=ItemOrder.Date, order_direction=OrderDirection.Descending)
        track_list = [format_track_data(track) for track in tracks]

        return jsonify({"tracks": track_list})
    except Exception as e:
        return jsonify({"error": f"Error fetching tracks: {str(e)}"}), 500


@app.route('/api/search', methods=['GET'])
@requires_tidal_auth
def search(session: BrowserSession):
    """
    Search TIDAL for tracks, albums, artists, and playlists.

    Query parameters:
        q: Search query (required)
        type: Type of content to search for - track, album, artist, playlist, or all (default: all)
        limit: Maximum number of results per type (default: 50, max: 300)
    """
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all').lower()
    limit = bound_limit(request.args.get('limit', default=50, type=int), max_n=300)

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        # Map search types to tidalapi models
        model_map = {
            'track': [tidalapi.Track],
            'album': [tidalapi.Album],
            'artist': [tidalapi.Artist],
            'playlist': [tidalapi.Playlist],
            'all': None  # None searches all types
        }

        models = model_map.get(search_type)
        if search_type not in model_map:
            return jsonify({"error": f"Invalid search type '{search_type}'. Must be one of: track, album, artist, playlist, all"}), 400

        results = session.search(query, models=models, limit=limit)

        response = {}

        # Handle top_hit - determine type and format appropriately
        top_hit = results.get('top_hit')
        if top_hit:
            # Check the type and format appropriately
            if isinstance(top_hit, tidalapi.media.Track):
                response['top_hit'] = {'type': 'track', 'data': format_track_data(top_hit)}
            elif isinstance(top_hit, tidalapi.album.Album):
                response['top_hit'] = {'type': 'album', 'data': format_album_data(top_hit)}
            elif isinstance(top_hit, tidalapi.artist.Artist):
                response['top_hit'] = {'type': 'artist', 'data': format_artist_data(top_hit)}
            elif isinstance(top_hit, tidalapi.playlist.Playlist):
                response['top_hit'] = {'type': 'playlist', 'data': format_playlist_data(top_hit)}

        # Format each result type (results is a dict, not an object)
        if results.get('tracks'):
            response['tracks'] = [format_track_data(t) for t in results['tracks']]
        if results.get('albums'):
            response['albums'] = [format_album_data(a) for a in results['albums']]
        if results.get('artists'):
            response['artists'] = [format_artist_data(a) for a in results['artists']]
        if results.get('playlists'):
            response['playlists'] = [format_playlist_data(p) for p in results['playlists']]

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


@app.route('/api/search/batch', methods=['POST'])
@requires_tidal_auth
def batch_search(session: BrowserSession):
    """
    Search TIDAL for multiple queries in a single request.
    Processes queries concurrently for efficiency.

    Expected JSON payload:
    {
        "queries": [
            {"query": "Bohemian Rhapsody", "type": "track"},
            {"query": "Yesterday Beatles", "type": "track"},
            ...
        ],
        "limit_per_query": 5  // Optional, default 5
    }

    Returns:
    {
        "results": [
            {"query": "...", "type": "track", "tracks": [...], "top_hit": {...}},
            ...
        ],
        "total": 50
    }
    """
    try:
        request_data = request.get_json()
        if not request_data or 'queries' not in request_data:
            return jsonify({"error": "Missing 'queries' in request body"}), 400

        queries = request_data['queries']
        limit_per_query = request_data.get('limit_per_query', 5)

        if not isinstance(queries, list) or len(queries) == 0:
            return jsonify({"error": "'queries' must be a non-empty list"}), 400

        if len(queries) > 100:
            return jsonify({"error": "Maximum 100 queries per batch"}), 400

        # Ensure limit is reasonable
        limit_per_query = min(max(1, limit_per_query), 20)

        def search_single(query_obj, search_session):
            """Search for a single query using the provided session"""
            q = query_obj.get('query', '') if isinstance(query_obj, dict) else str(query_obj)
            search_type = query_obj.get('type', 'track') if isinstance(query_obj, dict) else 'track'

            if not q:
                return {"query": q, "error": "Empty query"}

            try:
                model_map = {
                    'track': [tidalapi.Track],
                    'album': [tidalapi.Album],
                    'artist': [tidalapi.Artist],
                    'playlist': [tidalapi.Playlist],
                    'all': None
                }
                models = model_map.get(search_type.lower(), [tidalapi.Track])
                results = search_session.search(q, models=models, limit=limit_per_query)

                response = {"query": q, "type": search_type}

                # Format results based on type
                if results.get('tracks'):
                    response['tracks'] = [format_track_data(t) for t in results['tracks']]
                if results.get('albums'):
                    response['albums'] = [format_album_data(a) for a in results['albums']]
                if results.get('artists'):
                    response['artists'] = [format_artist_data(a) for a in results['artists']]
                if results.get('playlists'):
                    response['playlists'] = [format_playlist_data(p) for p in results['playlists']]

                # Include top_hit if available
                top_hit = results.get('top_hit')
                if top_hit:
                    if isinstance(top_hit, tidalapi.media.Track):
                        response['top_hit'] = {'type': 'track', 'data': format_track_data(top_hit)}
                    elif isinstance(top_hit, tidalapi.album.Album):
                        response['top_hit'] = {'type': 'album', 'data': format_album_data(top_hit)}
                    elif isinstance(top_hit, tidalapi.artist.Artist):
                        response['top_hit'] = {'type': 'artist', 'data': format_artist_data(top_hit)}

                return response
            except Exception as e:
                return {"query": q, "error": str(e)}

        # Process queries - use sequential processing to avoid tidalapi thread safety issues
        # This is still much faster than making 50+ MCP tool calls because we avoid
        # the MCP/HTTP overhead for each query
        results = []

        # Log progress for debugging
        print(f"Batch search: processing {len(queries)} queries", file=sys.stderr, flush=True)

        for i, q in enumerate(queries):
            try:
                result = search_single(q, session)
                results.append(result)
            except Exception as e:
                print(f"Batch search error on query {i}: {e}", file=sys.stderr, flush=True)
                q_str = q.get('query', str(q)) if isinstance(q, dict) else str(q)
                results.append({"query": q_str, "error": str(e)})

        print(f"Batch search: completed {len(results)} queries", file=sys.stderr, flush=True)

        return jsonify({"results": results, "total": len(results)})

    except Exception as e:
        return jsonify({"error": f"Batch search failed: {str(e)}"}), 500


@app.route('/api/recommendations/track/<track_id>', methods=['GET'])
@requires_tidal_auth
def get_track_recommendations(track_id: str, session: BrowserSession):
    """
    Get recommended tracks based on a specific track using TIDAL's track radio feature.
    """
    try:
        # Get limit from query parameter, default to 10 if not specified
        limit = bound_limit(request.args.get('limit', default=10, type=int))

        # Get recommendations using track radio
        track = session.track(track_id)
        if not track:
            return jsonify({"error": f"Track with ID {track_id} not found"}), 404

        recommendations = track.get_track_radio(limit=limit)

        # Format track data
        track_list = [format_track_data(track) for track in recommendations]
        return jsonify({"recommendations": track_list})
    except Exception as e:
        return jsonify({"error": f"Error fetching recommendations: {str(e)}"}), 500


@app.route('/api/recommendations/batch', methods=['POST'])
@requires_tidal_auth
def get_batch_recommendations(session: BrowserSession):
    """
    Get recommended tracks based on a list of track IDs using concurrent requests.
    """
    import concurrent.futures

    try:
        # Get request data
        request_data = request.get_json()
        if not request_data or 'track_ids' not in request_data:
            return jsonify({"error": "Missing track_ids in request body"}), 400

        track_ids = request_data['track_ids']
        if not isinstance(track_ids, list):
            return jsonify({"error": "track_ids must be a list"}), 400

        # Get limit per track from query parameter
        limit_per_track = bound_limit(request_data.get('limit_per_track', 20))

        # Optional parameter to remove duplicates across recommendations
        remove_duplicates = request_data.get('remove_duplicates', True)

        def get_track_recommendations(track_id):
            """Function to get recommendations for a single track"""
            try:
                track = session.track(track_id)
                recommendations = track.get_track_radio(limit=limit_per_track)
                # Format track data immediately
                formatted_recommendations = [
                    format_track_data(rec, source_track_id=track_id)
                    for rec in recommendations
                ]
                return formatted_recommendations
            except Exception as e:
                print(f"Error getting recommendations for track {track_id}: {str(e)}", file=sys.stderr, flush=True)
                return []

        all_recommendations = []
        seen_track_ids = set()

        # Use ThreadPoolExecutor to process tracks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(track_ids)) as executor:
            # Submit all tasks and map them to their track_ids
            future_to_track_id = {
                executor.submit(get_track_recommendations, track_id): track_id
                for track_id in track_ids
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_track_id):
                track_recommendations = future.result()

                # Add recommendations to the result list
                for track_data in track_recommendations:
                    track_id = track_data.get('id')

                    # Skip if we've already seen this track and want to remove duplicates
                    if remove_duplicates and track_id in seen_track_ids:
                        continue

                    all_recommendations.append(track_data)
                    seen_track_ids.add(track_id)

        return jsonify({"recommendations": all_recommendations})
    except Exception as e:
        return jsonify({"error": f"Error fetching batch recommendations: {str(e)}"}), 500


@app.route('/api/playlists', methods=['POST'])
@requires_tidal_auth
def create_playlist(session: BrowserSession):
    """
    Creates a new TIDAL playlist and adds tracks to it.

    Expected JSON payload:
    {
        "title": "Playlist title",
        "description": "Playlist description",
        "track_ids": [123456789, 987654321, ...]
    }

    Returns the created playlist information.
    """
    try:
        # Get request data
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Missing request body"}), 400

        # Validate required fields
        if 'title' not in request_data:
            return jsonify({"error": "Missing 'title' in request body"}), 400

        if 'track_ids' not in request_data or not request_data['track_ids']:
            return jsonify({"error": "Missing 'track_ids' in request body or empty track list"}), 400

        # Get parameters from request
        title = request_data['title']
        description = request_data.get('description', '')  # Optional
        track_ids = request_data['track_ids']

        # Validate track_ids is a list
        if not isinstance(track_ids, list):
            return jsonify({"error": "'track_ids' must be a list"}), 400

        # Create the playlist
        playlist = session.user.create_playlist(title, description)

        # Add tracks to the playlist
        playlist.add(track_ids)

        # Return playlist information
        playlist_info = {
            "id": playlist.id,
            "title": playlist.name,
            "description": playlist.description,
            "created": playlist.created,
            "last_updated": playlist.last_updated,
            "track_count": playlist.num_tracks,
            "duration": playlist.duration,
        }

        return jsonify({
            "status": "success",
            "message": f"Playlist '{title}' created successfully with {len(track_ids)} tracks",
            "playlist": playlist_info
        })

    except Exception as e:
        return jsonify({"error": f"Error creating playlist: {str(e)}"}), 500


@app.route('/api/playlists/<playlist_id>/tracks', methods=['POST'])
@requires_tidal_auth
def add_tracks_to_playlist(playlist_id: str, session: BrowserSession):
    """
    Add tracks to an existing TIDAL playlist.

    Expected JSON payload:
    {
        "track_ids": [123456789, 987654321, ...],
        "allow_duplicates": false  // optional, defaults to false
    }

    Returns the number of tracks added.
    """
    try:
        # Get request data
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Missing request body"}), 400

        # Validate required fields
        if 'track_ids' not in request_data or not request_data['track_ids']:
            return jsonify({"error": "Missing 'track_ids' in request body or empty track list"}), 400

        track_ids = request_data['track_ids']
        allow_duplicates = request_data.get('allow_duplicates', False)

        # Validate track_ids is a list
        if not isinstance(track_ids, list):
            return jsonify({"error": "'track_ids' must be a list"}), 400

        # Get the playlist
        playlist = session.playlist(playlist_id)
        if not playlist:
            return jsonify({"error": f"Playlist with ID {playlist_id} not found"}), 404

        # Add tracks to the playlist
        added_ids = playlist.add(track_ids, allow_duplicates=allow_duplicates)

        return jsonify({
            "status": "success",
            "message": f"Added {len(added_ids)} tracks to playlist",
            "playlist_id": playlist_id,
            "tracks_added": len(added_ids)
        })

    except Exception as e:
        return jsonify({"error": f"Error adding tracks to playlist: {str(e)}"}), 500


@app.route('/api/playlists', methods=['GET'])
@requires_tidal_auth
def get_user_playlists(session: BrowserSession):
    """
    Get the user's playlists from TIDAL.
    """
    try:
        # Get user playlists
        playlists = session.user.playlists()

        # Format playlist data
        playlist_list = []
        for playlist in playlists:
            playlist_info = {
                "id": playlist.id,
                "title": playlist.name,
                "description": playlist.description if hasattr(playlist, 'description') else "",
                "created": playlist.created if hasattr(playlist, 'created') else None,
                "last_updated": playlist.last_updated if hasattr(playlist, 'last_updated') else None,
                "track_count": playlist.num_tracks if hasattr(playlist, 'num_tracks') else 0,
                "duration": playlist.duration if hasattr(playlist, 'duration') else 0,
                "url": f"https://tidal.com/playlist/{playlist.id}"
            }
            playlist_list.append(playlist_info)

        # Sort playlists by last_updated in descending order
        sorted_playlists = sorted(
            playlist_list,
            key=lambda x: x.get('last_updated', ''),
            reverse=True
        )

        return jsonify({"playlists": sorted_playlists})
    except Exception as e:
        return jsonify({"error": f"Error fetching playlists: {str(e)}"}), 500


@app.route('/api/playlists/<playlist_id>/tracks', methods=['GET'])
@requires_tidal_auth
def get_playlist_tracks(playlist_id: str, session: BrowserSession):
    """
    Get tracks from a specific TIDAL playlist.

    Query parameters:
        limit: Maximum number of tracks to return (default: 100, max: 500)
        offset: Starting index for pagination (default: 0)
    """
    try:
        # Get limit and offset from query parameters
        # Allow up to 500 tracks per request for comprehensive playlist retrieval
        limit = bound_limit(request.args.get('limit', default=100, type=int), max_n=500)
        offset = request.args.get('offset', default=0, type=int)
        if offset < 0:
            offset = 0

        # Get the playlist object
        playlist = session.playlist(playlist_id)
        if not playlist:
            return jsonify({"error": f"Playlist with ID {playlist_id} not found"}), 404

        # Get total track count from playlist metadata
        total_available = playlist.num_tracks if hasattr(playlist, 'num_tracks') else 0

        # Get tracks from the playlist with pagination
        tracks = playlist.items(limit=limit, offset=offset)

        # Format track data
        track_list = [format_track_data(track) for track in tracks]

        return jsonify({
            "playlist_id": playlist.id,
            "tracks": track_list,
            "total_tracks": len(track_list),
            "total_available": total_available,
            "offset": offset,
            "limit": limit
        })

    except Exception as e:
        return jsonify({"error": f"Error fetching playlist tracks: {str(e)}"}), 500


@app.route('/api/playlists/<playlist_id>', methods=['DELETE'])
@requires_tidal_auth
def delete_playlist(playlist_id: str, session: BrowserSession):
    """
    Delete a TIDAL playlist by its ID.
    """
    try:
        # Get the playlist object
        playlist = session.playlist(playlist_id)
        if not playlist:
            return jsonify({"error": f"Playlist with ID {playlist_id} not found"}), 404

        # Delete the playlist
        playlist.delete()

        return jsonify({
            "status": "success",
            "message": f"Playlist with ID {playlist_id} was successfully deleted"
        })

    except Exception as e:
        return jsonify({"error": f"Error deleting playlist: {str(e)}"}), 500


# =============================================================================
# Download Endpoints (using tidal-dl-ng)
# Note: These endpoints do NOT use @requires_tidal_auth because tidal-dl-ng
# has its own separate authentication via 'tdn login'
# =============================================================================

@app.route('/api/download/status', methods=['GET'])
def get_download_status():
    """
    Check if tidal-dl-ng is installed and ready for downloads.
    """
    try:
        status = check_tdn_installed()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": f"Error checking tdn status: {str(e)}"}), 500


@app.route('/api/download/track', methods=['POST'])
def download_track():
    """
    Download a track using tidal-dl-ng.

    Expected JSON payload:
    {
        "track_id": "123456789"
    }
    """
    try:
        request_data = request.get_json()
        if not request_data or 'track_id' not in request_data:
            return jsonify({"error": "Missing 'track_id' in request body"}), 400

        track_id = str(request_data['track_id'])
        url = build_tidal_url('track', track_id)

        result = execute_tdn_download(url, timeout=300)

        if result['status'] == 'success':
            return jsonify({
                "status": "success",
                "message": f"Track {track_id} downloaded successfully",
                "url": url,
                "output": result.get('stdout', '')
            })
        else:
            status_code = 500 if 'not installed' in result.get('message', '') else 400
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": f"Error downloading track: {str(e)}"}), 500


@app.route('/api/download/album', methods=['POST'])
def download_album():
    """
    Download an album using tidal-dl-ng.

    Expected JSON payload:
    {
        "album_id": "123456789"
    }
    """
    try:
        request_data = request.get_json()
        if not request_data or 'album_id' not in request_data:
            return jsonify({"error": "Missing 'album_id' in request body"}), 400

        album_id = str(request_data['album_id'])
        url = build_tidal_url('album', album_id)

        result = execute_tdn_download(url, timeout=600)

        if result['status'] == 'success':
            return jsonify({
                "status": "success",
                "message": f"Album {album_id} downloaded successfully",
                "url": url,
                "output": result.get('stdout', '')
            })
        else:
            status_code = 500 if 'not installed' in result.get('message', '') else 400
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": f"Error downloading album: {str(e)}"}), 500


@app.route('/api/download/playlist', methods=['POST'])
def download_playlist_content():
    """
    Download a playlist using tidal-dl-ng.

    Expected JSON payload:
    {
        "playlist_id": "uuid-string-here"
    }
    """
    try:
        request_data = request.get_json()
        if not request_data or 'playlist_id' not in request_data:
            return jsonify({"error": "Missing 'playlist_id' in request body"}), 400

        playlist_id = str(request_data['playlist_id'])
        url = build_tidal_url('playlist', playlist_id)

        result = execute_tdn_download(url, timeout=1200)

        if result['status'] == 'success':
            return jsonify({
                "status": "success",
                "message": f"Playlist {playlist_id} downloaded successfully",
                "url": url,
                "output": result.get('stdout', '')
            })
        else:
            status_code = 500 if 'not installed' in result.get('message', '') else 400
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": f"Error downloading playlist: {str(e)}"}), 500


@app.route('/api/download/favorites', methods=['POST'])
def download_favorites():
    """
    Download favorites using tidal-dl-ng.

    Expected JSON payload:
    {
        "type": "tracks"  # or "albums", "artists", "videos"
    }
    """
    try:
        request_data = request.get_json()
        if not request_data or 'type' not in request_data:
            return jsonify({"error": "Missing 'type' in request body"}), 400

        fav_type = str(request_data['type']).lower()

        result = execute_tdn_download_favorites(fav_type, timeout=1800)

        if result['status'] == 'success':
            return jsonify({
                "status": "success",
                "message": f"Favorite {fav_type} downloaded successfully",
                "output": result.get('stdout', '')
            })
        else:
            status_code = 500 if 'not installed' in result.get('message', '') else 400
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": f"Error downloading favorites: {str(e)}"}), 500


if __name__ == '__main__':
    import os

    # Get port from environment variable or use default
    port = int(os.environ.get("TIDAL_MCP_PORT", 5050))

    print(f"Starting Flask app on port {port}", file=sys.stderr, flush=True)
    # use_reloader=False prevents Flask from spawning a child process that can
    # become a zombie if the parent dies unexpectedly, causing stale code issues
    app.run(debug=False, port=port, threaded=True, use_reloader=False)
