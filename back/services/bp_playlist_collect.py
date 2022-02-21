import logging
import os
import re

import spotipy
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from spotipy import SpotifyOAuth

from typing import List, Optional

from pydantic import BaseModel


class ArtistModel(BaseModel):
    id: str
    name: str


class TrackModel(BaseModel):
    title: str
    artists: List[str]
    artists_clear: List[str]


class PlaylistModel(BaseModel):
    id: str
    title: str
    tracks: Optional[List[TrackModel]]


class BeatportTrackModel(TrackModel):
    remixed: str
    track_id: Optional[str]
    track_url: Optional[str]


class SpotifyTrackModel(TrackModel):
    id: str
    url: str


logger = logging.getLogger("collector")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("app_logs/new.log")
handler.setLevel(logging.DEBUG)
handler_st = logging.StreamHandler()
handler_st.setLevel(logging.DEBUG)
strfmt = "[%(asctime)s] [%(name)s] [%(levelname)s] > %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(fmt=strfmt, datefmt=datefmt)
handler.setFormatter(formatter)
handler_st.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(handler_st)


def create_sp():
    scope = "playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))


def get_playlist_title(html_path) -> str:
    with open(html_path, "r", encoding="utf-8") as html_file:
        soup = BeautifulSoup(html_file, "html.parser")
        playlist_name = soup.find(class_="library-playlist__name").text
    return playlist_name


def clear_artists_name(artists: List[str]) -> List[str]:
    return [artist.strip().lower() for artist in artists]


def get_tracks(html_path) -> List[BeatportTrackModel]:
    tracks = []
    with open(html_path, "r", encoding="utf-8") as html_file:
        soup = BeautifulSoup(html_file, "html.parser")
        html_tracks = soup.find_all(class_="tracks__item")
        for track in html_tracks:
            title = track.find(class_="track-title__primary").text
            remixed = track.find(class_="track-title__remixed").text
            artists = [
                artist.text
                for artist in track.find_all(class_="track-artists__artist")
            ]
            track = BeatportTrackModel(
                title=title,
                remixed=remixed,
                artists=artists,
                artists_clear=clear_artists_name(artists),
            )
            tracks.append(track)
    return tracks


def create_playlist(sp, html_file_path) -> PlaylistModel:
    try:
        playlist_title = get_playlist_title(html_file_path)
    except AttributeError:
        playlist_title = "New Playlist Auto"

    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user_id, playlist_title)
    spoti_playlist = PlaylistModel(id=playlist["id"], title=playlist_title)
    return spoti_playlist


def create_search_string(track: BeatportTrackModel):
    is_extended = "Extended" if track.remixed == "Extended Mix" else ""
    search_str = f"{track.title} {' '.join(track.artists)} {is_extended}".strip()
    search_str = search_str.replace("feat.", "")
    search_str = re.sub(r" +", " ", search_str)
    return search_str


def search_string(sp, search_str: str):
    spoti_result = sp.search(q=search_str, type="track", limit=1)
    return spoti_result["tracks"]["items"]


def search_track(sp, track: BeatportTrackModel):
    search_str = f"'{create_search_string(track)}'"
    return search_string(sp, search_str)


def form_spoti_track(track: dict) -> SpotifyTrackModel:
    artists = [artist["name"] for artist in track["artists"]]
    return SpotifyTrackModel(
        title=track["name"],
        artists=artists,
        artists_clear=clear_artists_name(artists),
        id=track["id"],
        url=track["external_urls"]["spotify"],
    )


def save_spoti_tracks(sp, playlist: PlaylistModel, tracks: List[SpotifyTrackModel]):
    tracks_id = [track.id for track in tracks]
    sp.playlist_add_items(playlist.id, tracks_id)


def search_in_spotify(
    sp, tracks: List[BeatportTrackModel]
) -> tuple[List[SpotifyTrackModel], List[BeatportTrackModel]]:
    good_result = []
    empty_result = []
    for track in tracks:
        found_tracks = search_track(sp, track)
        if found_tracks:
            spoti_track = form_spoti_track(found_tracks[0])
            good_result.append(spoti_track)
        else:
            logger.info(f"Track Not Found : {track}")
            empty_result.append(track)

    return good_result, empty_result


def save_report(tracks: List[BeatportTrackModel], report_path: str):
    with open(report_path, "w", encoding="utf-8") as report_file:
        for track in tracks:
            report_file.write(f"{create_search_string(track)} :: {track}\n")


if __name__ == "__main__":
    load_dotenv()
    file_path = os.getenv("HEAP_FILE_PATH")
    report_path = "reports/report.txt"

    spotify = create_sp()
    new_playlist = create_playlist(spotify, file_path)
    logger.info(f"Create playlist : {new_playlist}")
    beatport_tracks = get_tracks(file_path)
    logger.info(f"Collect {beatport_tracks=} tracks from Beatport")
    spoti_tracks, not_found = search_in_spotify(spotify, beatport_tracks)
    logger.info(f"Found on Spotify : {len(spoti_tracks)}")
    logger.info(f"Not Found on Spotify : {len(not_found)}")
    save_spoti_tracks(spotify, new_playlist, spoti_tracks)
    save_report(not_found, report_path)
