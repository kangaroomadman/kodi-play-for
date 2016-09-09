import sys
import xbmcgui
import urlparse
import time
import json
import xbmc
import xbmcaddon


class PlayForPlayer(xbmc.Player):
    """Extension to xbmc.Player to store flags when playback starts and has
       been requested to stop."""
    def __init__(self):
        """Initialise the started and stopped flags."""
        xbmc.Player.__init__(self)
        self.started = False
        self.stopped = False

    def onPlayBackStarted(self):
        """Change the started flag once playback has begun."""
        self.started = True

    def onPlayBackStopped(self):
        """Change the stopped flag if the user has requested the playback to
           stop."""
        self.stopped = True


def log(message):
    """Log a message to the Kodi log."""
    xbmc.log('[%s]: %s' % (xbmcaddon.Addon().getAddonInfo('name'), message))


def play(seconds):
    """Play videos for a set number of seconds."""
    # Extract the TV show ID from the path
    path = sys.listitem.getfilename()
    path_arguments = urlparse.parse_qs(urlparse.urlparse(path).query)
    tv_show = str(path_arguments['tvshowid'][0])
    log('Extracted TV show ID of %s from \'%s\'.' % (tv_show, path))

    # Get the season and episode numbers
    this_season = int(xbmc.getInfoLabel('ListItem.Season'))
    this_episode = int(xbmc.getInfoLabel('ListItem.Episode'))
    log('Calculated start season as %d and episode as %d.' %
        (this_season, this_episode))

    # Get the TV episodes
    json_request = '''\
    {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetEpisodes",
        "params":
        {
            "tvshowid": %s,
            "properties":
            [
                "episode", "season", "file", "resume", "streamdetails"
            ]
        },
        "id": 1
        }
    ''' % tv_show
    json_reply = xbmc.executeJSONRPC(json_request).decode('utf-8', 'replace')
    episodes = json.loads(json_reply)['result']['episodes']
    # Sort them in season,episode order
    episodes.sort(key=lambda e: (e['season'] * 100) + e['episode'])
    log('Found %d episodes for current TV show.' % len(episodes))

    # Iterate over episodes and create a playlist
    playlist_runtime = 0
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    for episode in episodes:
        # Only start when we've reached the current season and episode
        if not((int(episode['season']) < this_season) or
               ((int(episode['season']) == this_season) and
                (int(episode['episode']) < this_episode))):
            # Get the episode runtime
            runtime = int(episode['streamdetails']['video'][0]['duration'])

            # Create a new list item to add to a playlist
            item = xbmcgui.ListItem(episode['label'])

            # Only resume the first episode
            if playlist.size() == 0:
                resume = episode['resume']['position']
                item.setProperty('StartOffset', str(resume))
                # We're resuming this episode, so re-calculate the runtime
                runtime -= int(resume)

            # Accumulate the playlist runtime
            playlist_runtime += runtime

            # Add to the playlist
            log('Adding S%02dE%02d with runtime of '
                '%ds to the playlist (total runtime = %ds).' %
                (episode['season'],
                 episode['episode'],
                 runtime,
                 playlist_runtime))
            playlist.add(episode['file'], item)

            # Only make the playlist as long as it needs to be
            if playlist_runtime > seconds:
                break
    log('Created playlist with %d episodes.' % playlist.size())

    # Start playing the playlist
    player = PlayForPlayer()
    player.play(playlist)

    # Wait until the player has started
    while not player.started:
        xbmc.sleep(1000)
    log('Playback has started.')

    # If the playlist runtime is greater than the desired time then sleep until
    # we need to stop
    if playlist_runtime > seconds:
        log('Playlist is longer than desired runtime. '
            'Waiting to ensure playlist is stopped at correct point.')
        start = time.time()
        end = start + seconds
        while 1:
            # Wait until the end of the period or user requests a stop
            xbmc.sleep(1000)
            if time.time() >= end:
                log('Requested time has elapsed. Stopping playback.')
                player.stop()
                break
            if player.stopped:
                log('User has stopped playlist early.')
                break
