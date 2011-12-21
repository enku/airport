"""
Context processors for the Airport app
"""

from django.conf import settings

EXTERNALS = {
    'jquery': 'https://ajax.googleapis.com/ajax/libs/jquery/1.7.0/jquery.min.js',
    'jquery_ui': 'https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.16/jquery-ui.min.js',
    'jquery_scrollto': 'http://flesler-plugins.googlecode.com/files/jquery.scrollTo-1.4.2-min.js',
    'jquery_cookie': 'https://raw.github.com/carhartl/jquery-cookie/master/jquery.cookie.js',
    'login_icon': 'http://www.ercmp.nic.in/images/login.png',
    'login_button': 'http://tahatunga.net/downloads/icon/order/Concept_Icon_Set/Buttons/PNG/Button-Log%20off.png',
    'register_icon': 'https://help.ess.msu.edu/themes/client_default/063684-green-metallic-orb-icon-people-things-handshake.png',
    'background_image': 'http://images2.layoutsparks.com/1/238605/moon-over-mistral-sky.jpg',
    'inflight_image': 'http://av-mech.com/images/flyinganimated_20airplane.gif',
    'landed_sound': 'http://soundbible.com/mp3/757 Landing-SoundBible.com-1539957439.mp3',
    'takeoff_sound': 'http://soundbible.com/mp3/757 Landing-SoundBible.com-1539957439.mp3',
    'gold_star': 'http://njwltech.wikispaces.com/file/view/gold_star.png/35350229/gold_star.png',
    'inbox_icon': 'http://starsvet.com/templates/tmpl_ae4/images_ae4/write_message.gif',
    'inbox_sound': 'http://soundbible.com/mp3/A-Tone-His_Self-1266414414.mp3',
    'ticket_sound': 'http://soundbible.com/mp3/Cash Register Cha Ching-SoundBible.com-184076484.mp3',
    'finished_image': 'http://www.moodiereport.com/images2/munich_airport_600px_dec09.jpg',
    'notification_icon': 'http://icons.iconarchive.com/icons/icons-land/points-of-interest/64/Airport-Blue-icon.png',

    # messages
    'message_MONKEYWRENCH_sound': 'http://www.freesound.org/data/previews/17/17468_57789-lq.mp3',
    'message_DEFAULT_sound': 'http://soundbible.com/mp3/A-Tone-His_Self-1266414414.mp3',
    'message_GOAL_sound': 'http://soundbible.com/mp3/Kids Cheering-SoundBible.com-681813822.mp3',
    'message_GAMEOVER_sound': 'http://www.freesound.org/data/previews/42/42349_81909-lq.mp3',
    'message_WINNER_sound': 'http://soundbible.com/mp3/Ta Da-SoundBible.com-1884170640.mp3'
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
