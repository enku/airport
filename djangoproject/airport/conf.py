"""App-specific settings for Airport"""

from django.conf import settings as django_settings

USER_SETTINGS = getattr(django_settings, 'AIRPORT', None)

DEFAULTS = {
    'GAME_NAME': 'Airport',
    'MINUTES_BEFORE_BOARDING': 10,
    'MAX_SESSION_MESSAGES': 16,
    'SCALE_FLIGHT_TIMES': False,
    'MIN_FLIGHT_TIME': 30,
    'MAX_FLIGHT_TIME': None,
    'CRUISE_SPEED': 13.0,  # km/min (Boeing 737)
    'AI_USERNAMES': 'Guy Miles',
    'GAME_HISTORY_COUNT': 15,
    'MAX_TIME_BETWEEN_WRENCHES': 45,  # seconds
    'AIRPORT_REPO_URL': 'https://bitbucket.org/marduk/airport',
    'MAP_INITIAL_LATITUDE': 39.83,
    'MAP_INITIAL_LONGITUDE': -98.58,
    'MAP_INITIAL_ZOOM': 4,
    'WEBSOCKET_PORT': 8080,
    'GAMESERVER_LOOP_DELAY': 4,
    'GAMESERVER_MULTIPROCESSING': False,
    'GAMESERVER_HOST': 'localhost',
    'TIMEFACTOR': 60,

    'EXTERNALS': {
        'jquery': 'https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js',
        'jquery_ui': 'https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/jquery-ui.min.js',
        'jquery_ui_css': 'https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/themes/base/jquery-ui.css',
        'jquery_scrollto': 'http://flesler-plugins.googlecode.com/files/jquery.scrollTo-1.4.2-min.js',
        'jquery_cookie': '//cdn.jsdelivr.net/jquery.cookie/1.4.0/jquery.cookie.min.js',
        'mustache_js': '//cdn.jsdelivr.net/mustache.js/0.7.3/mustache.js',
        'login_icon': 'http://www.ercmp.nic.in/images/login.png',
        'login_button': 'http://www.iconhot.com/icon/png/i-buttons-3c/64/bright-ball-logoff.png',
        'register_icon': 'http://www.shs.rcs.k12.tn.us/registrationIcon.png',
        'background_image': 'https://thisishasna.files.wordpress.com/2012/09/moon-over-mistral-sky.jpg',
        'flight_video': 'http://www.grobergreen.com/wp-content/uploads/2009/07/WD0193.webm',
        'inflight_image': 'https://media.giphy.com/media/vtOP26LcbWyCA/giphy.gif',
        'landed_sound': 'http://soundbible.com/mp3/757%20Landing-SoundBible.com-1539957439.mp3',
        'takeoff_sound': 'http://soundbible.com/mp3/757%20Landing-SoundBible.com-1539957439.mp3',
        'gold_star': 'http://njwltech.wikispaces.com/file/view/gold_star.png/35350229/gold_star.png',
        'ticket_sound': 'http://soundbible.com/mp3/Cash%20Register%20Cha%20Ching-SoundBible.com-184076484.mp3',
        'finished_image': 'http://www.moodiereport.com/images2/munich_airport_600px_dec09.jpg',
        'notification_icon': 'http://icons.iconarchive.com/icons/icons-land/points-of-interest/64/Airport-Blue-icon.png',
        'medal': 'http://www.clker.com/cliparts/R/A/q/t/b/L/gold-medal-md.png',
        'notepad_cursor': 'http://www.cursor.cc/cursor/154/0/cursor.png',
        'button_click': 'http://soundbible.com/mp3/Air%20Plane%20Ding-SoundBible.com-496729130.mp3',
        'pause_icon': 'http://icons.iconarchive.com/icons/icons-land/play-stop-pause/256/Pause-Normal-icon.png',
        'green_dot': 'http://www.google.com/intl/en_us/mapfiles/ms/micons/green-dot.png',

        # message sounds
        'message_MONKEYWRENCH_sound': 'http://www.freesound.org/data/previews/17/17468_57789-lq.mp3',
        'message_ERROR_sound': 'http://www.freesound.org/data/previews/17/17468_57789-lq.mp3',
        'message_DEFAULT_sound': 'http://soundbible.com/mp3/A-Tone-His_Self-1266414414.mp3',
        'message_GOAL_sound': 'http://soundbible.com/mp3/Kids%20Cheering-SoundBible.com-681813822.mp3',
        'message_GAMEOVER_sound': 'http://www.freesound.org/data/previews/42/42349_81909-lq.mp3',
        'message_WINNER_sound': 'http://soundbible.com/mp3/Ta%20Da-SoundBible.com-1884170640.mp3',
        'message_NEWGAME_sound': 'http://soundbible.com/mp3/flyby-Conor-1500306612.mp3',

        # message icons
        'message_DEFAULT_icon': 'http://i.imgur.com/weyIX.png',
        'message_MONKEYWRENCH_icon': 'http://i.imgur.com/lmbJs.png',
        'message_ERROR_icon': 'http://i.imgur.com/lmbJs.png',
        'message_PLAYERACTION_icon': 'http://i.imgur.com/yTUkp.png',
        'message_GOAL_icon': 'http://i.imgur.com/yTUkp.png',
        'message_NEWGAME_icon': 'http://i.imgur.com/yTUkp.png',
        'message_WINNER_icon': 'http://i.imgur.com/yTUkp.png',
    },
}


class AirportSettings(object):
    def __init__(self, user_settings=None, defaults=None):
        self.user_settings = user_settings or {}
        self.defaults = defaults or {}

    def __getattr__(self, attr):
        if attr not in self.defaults.keys():
            raise AttributeError(attr)

        try:
            val = self.user_settings[attr]
        except KeyError:
            val = self.defaults[attr]

        val = self.validate_setting(attr, val)
        setattr(self, attr, val)
        return val

    def validate_setting(self, attr, val):
        return val


settings = AirportSettings(USER_SETTINGS, DEFAULTS)
