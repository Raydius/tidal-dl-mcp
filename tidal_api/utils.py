def _get_name_from_attr(obj, attr_name, default="Unknown"):
    """
    Safely extract a name from an object attribute that may be an object with .name,
    a string, or missing entirely.
    """
    if not hasattr(obj, attr_name):
        return default

    attr = getattr(obj, attr_name)
    if attr is None:
        return default
    if hasattr(attr, 'name'):
        return attr.name if attr.name else default
    if isinstance(attr, str):
        return attr if attr else default
    # Fallback: convert to string
    return str(attr) if attr else default


def format_track_data(track, source_track_id=None):
    """
    Format a track object into a standardized dictionary.

    Args:
        track: TIDAL track object
        source_track_id: Optional ID of the track that led to this recommendation

    Returns:
        Dictionary with standardized track information
    """
    track_data = {
        "id": track.id,
        "title": track.name,
        "artist": _get_name_from_attr(track, 'artist'),
        "album": _get_name_from_attr(track, 'album'),
        "duration": track.duration if hasattr(track, 'duration') else 0,
        "url": f"https://tidal.com/browse/track/{track.id}?u"
    }

    # Include source track ID if provided
    if source_track_id:
        track_data["source_track_id"] = source_track_id

    return track_data

def bound_limit(limit: int, max_n: int = 50) -> int:
    # Ensure limit is within reasonable bounds
    if limit < 1:
        limit = 1
    elif limit > max_n:
        limit = max_n
    print(f"Limit set to {limit} (max {max_n})")
    return limit


def format_album_data(album):
    """
    Format an album object into a standardized dictionary.

    Args:
        album: TIDAL album object

    Returns:
        Dictionary with standardized album information
    """
    return {
        "id": album.id,
        "title": album.name,
        "artist": _get_name_from_attr(album, 'artist'),
        "release_date": str(album.release_date) if hasattr(album, 'release_date') and album.release_date else None,
        "num_tracks": album.num_tracks if hasattr(album, 'num_tracks') else 0,
        "duration": album.duration if hasattr(album, 'duration') else 0,
        "url": f"https://tidal.com/browse/album/{album.id}"
    }


def format_artist_data(artist):
    """
    Format an artist object into a standardized dictionary.

    Args:
        artist: TIDAL artist object

    Returns:
        Dictionary with standardized artist information
    """
    return {
        "id": artist.id,
        "name": artist.name,
        "url": f"https://tidal.com/browse/artist/{artist.id}"
    }


def format_playlist_data(playlist):
    """
    Format a playlist object into a standardized dictionary.

    Args:
        playlist: TIDAL playlist object

    Returns:
        Dictionary with standardized playlist information
    """
    return {
        "id": playlist.id,
        "title": playlist.name,
        "description": playlist.description if hasattr(playlist, 'description') else "",
        "num_tracks": playlist.num_tracks if hasattr(playlist, 'num_tracks') else 0,
        "duration": playlist.duration if hasattr(playlist, 'duration') else 0,
        "url": f"https://tidal.com/playlist/{playlist.id}"
    }
