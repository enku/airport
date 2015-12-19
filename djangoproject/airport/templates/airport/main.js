
function main($) {
    /* document.ready function */

    /* prefetch the animated image */
    var inflight_image = new Image();
    inflight_image.src = '{{ inflight_image }}';

	//$('#airport_screen').toggle('slide', {direction: 'down'});
    $('#goals_range')[0].oninput = airport.update_goals_slider;
    $('#airports_range')[0].oninput = airport.update_airports_slider;

    $('#progress').progressbar({value: 0});

    //$('#notepad').memdraggable({handle: '.header'}).memresizable();

    $('#frm').submit(airport.buy_ticket);
    $('#create_form').submit(airport.create_game);
    $('#pause').click(airport.post_link);
    $('#resume').click(airport.post_link);
    $('#ragequit').click(airport.post_link);

    airport.messages('#message_box');
    airport.websocket_connect('home');
    airport.get_geography();
    setInterval(airport.games_screen_interval_cb, 30000);

    $.ajax({
        type: 'GET',
        success: airport.refresh_ui,
        url: '{% url "info" %}'
    });
    $('#my_stats_widget').load('{% url "airport.views.games_stats" %}');
}


jQuery(document).ready(main);
