
function main($) {
    /* document.ready function */
	//$('#airport_screen').toggle('slide', {direction: 'down'});
    $('#goals_range').change(airport.update_goals_slider);
    $('#airports_range').change(airport.update_airports_slider);

    $('#progress').progressbar({value: 0});

    //$('#notepad').memdraggable({handle: '.header'}).memresizable();

    $('#frm').submit(airport.buy_ticket);
    $('#create_form').submit(airport.create_game);
    $('#pause').click(airport.post_link);
    $('#resume').click(airport.post_link);
    $('#ragequit').click(airport.post_link);

    airport.messages('#message_box');
    airport.websocket_connect('home');
    setInterval(airport.games_screen_interval_cb, 30000);

    $.ajax({
        type: 'GET',
        success: airport.refresh_ui,
        url: '{% url "info" %}'
    });
    $('#my_stats_widget').load('{% url "airport.views.games_stats" %}');
}


jQuery(document).ready(main);
