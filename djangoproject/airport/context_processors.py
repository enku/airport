"""
Context processors for the Airport app
"""

from django.conf import settings

EXTERNALS = {
    'jquery': 'https://ajax.googleapis.com/ajax/libs/jquery/1.7.0/jquery.min.js',
    'jquery_ui': 'https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/jquery-ui.min.js',
    'jquery_ui_css': 'https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/themes/base/jquery-ui.css',
    'jquery_scrollto': 'http://flesler-plugins.googlecode.com/files/jquery.scrollTo-1.4.2-min.js',
    'jquery_cookie': '//cdn.jsdelivr.net/jquery.cookie/1.4.0/jquery.cookie.min.js',
    'mustache_js': '//cdn.jsdelivr.net/mustache.js/0.7.3/mustache.js',
    'login_icon': 'http://www.ercmp.nic.in/images/login.png',
    'login_button': 'http://www.iconhot.com/icon/png/i-buttons-3c/64/bright-ball-logoff.png',
    'register_icon': 'https://help.ess.msu.edu/themes/client_default/063684-green-metallic-orb-icon-people-things-handshake.png',
    'background_image': 'http://images2.layoutsparks.com/1/238605/moon-over-mistral-sky.jpg',
    'inflight_image': 'http://paysonairport.com/images/AnimatedAirplane.gif',
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
    'message_DEFAULT_icon': 'http://starsvet.com/templates/tmpl_ae4/images_ae4/write_message.gif',
    'message_MONKEYWRENCH_icon': 'http://sourceforge.net/apps/trac/xoops/export/1811/XoopsModules/newbb/trunk/templates/images/icon/topic_hot_new.gif',
    'message_ERROR_icon': 'http://sourceforge.net/apps/trac/xoops/export/1811/XoopsModules/newbb/trunk/templates/images/icon/topic_hot_new.gif',
    'message_PLAYERACTION_icon': 'http://swiftheartrabbit.home.comcast.net/~swiftheartrabbit/Graphics/Main%20Graphics/Open%20Topic.gif',
    'message_GOAL_icon': 'http://swiftheartrabbit.home.comcast.net/~swiftheartrabbit/Graphics/Main%20Graphics/Open%20Topic.gif',
    'message_NEWGAME_icon': 'http://swiftheartrabbit.home.comcast.net/~swiftheartrabbit/Graphics/Main%20Graphics/Open%20Topic.gif',
    'message_WINNER_icon': 'http://swiftheartrabbit.home.comcast.net/~swiftheartrabbit/Graphics/Main%20Graphics/Open%20Topic.gif',
}


def externals(request):
    """Exernal files, like javascript and images.  Stuff we want to use but
    not host ourselves"""
    context_extras = {}
    external_settings = getattr(settings, 'AIRPORT_EXTERNALS', EXTERNALS)

    for external in EXTERNALS:
        context_extras[external] = external_settings.get(external,
                                                         EXTERNALS[external])

    return context_extras
