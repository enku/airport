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
    'gold_star': 'http://njwltech.wikispaces.com/file/view/gold_star.png/35350229/gold_star.png',
    'inbox_icon': 'http://starsvet.com/templates/tmpl_ae4/images_ae4/write_message.gif',
    'inbox_sound': 'http://www.freesound.org/data/previews/53/53268_382028-lq.mp3',
    'finished_image': 'http://www.moodiereport.com/images2/munich_airport_600px_dec09.jpg',
    'notification_icon': 'http://icons.iconarchive.com/icons/icons-land/points-of-interest/64/Airport-Blue-icon.png'
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
