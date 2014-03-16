var airport = window.airport || {};

airport.background_image = new Image();
airport.current_goal = null;
airport.goldstar = "{{ gold_star }}";
airport.last_ticket = null;
airport.paused = null;

// XXX: Clean up!
airport.refresh_ui = function (data)
{
    "use strict";
    var lightbox,
        content;

    if (data.current_game === null) {
        airport.games_screen(data);
    } else if (data.in_flight === false) {
        airport.airport_screen(data);
    } else if (data.in_flight === true) {
        airport.flight_screen(data);
    } else if (data.current_state === 'hosting') {
        airport.games_screen(data);
        $('#create_widget').hide();
        // display the start game lightbox
        // XXX: This is refreshing every time... we don't want that
        lightbox = new airport.LightBox('#lightbox_content');
        lightbox.content.html(Mustache.render($('#start_game').html(), {
            game_id: data.current_game,
            image: '{{ inflight_image }}',
            url: '{% url "start_game" %}'
        }));
        lightbox.show();
    } else if (data.current_state === 'waiting') {
        airport.games_screen(data);
        $('#create_widget').hide();
        // XXX: This is refreshing every time... we don't want that
        lightbox = new airport.LightBox('#lightbox_content');
        lightbox.content.html(Mustache.render($('#wait_for_game').html(), {
            game_id: data.current_game,
            image: '{{ inflight_image }}'
        }));
        lightbox.show();
    } else {
        console.log('*** refresh_ui(): unhandled condition: ***');
        console.log(data);
    }
};


airport.games_screen = function (data)
{
    "use strict";
    var $create_widget = $('#create_widget');

    $('.in_game').hide();
    airport.show_screen('games');
    airport.update_games_menu(data.games);

    if (data.current_state !== 'open') {
        $create_widget.hide();
    } else {
        $create_widget.show();
    }
};

airport.flight_screen = function (data)
{
    "use strict";
    var city_image_url;

    $('.in_game').show();
    $('.out_game').hide();
    airport.show_screen('flight', '{{ takeoff_sound }}');

    if (data.city) {
        city_image_url = ('{% url "city_image" %}' + encodeURIComponent(data.city) + '/');
        airport.preload_image(city_image_url);
    }

    airport.change_background($('#airport_screen'), city_image_url);

    /* update progress bar */
    $( "#progress" ).progressbar("value", data.percentage);

    // ticket widget
    airport.update_ticket_widget(data.ticket, data.player);
    
    airport.update_panel(data);

    if (data.game_state === 'Paused') {
        airport.paused = airport.paused || new airport.LightBox('#lightbox_content');
        airport.paused.show();
    } else if (airport.paused) {
        airport.paused.hide();
        airport.paused = null;
    }
};

airport.airport_screen = function (data)
{
    "use strict";
    var city_image_url,
        current_goal,
        lightbox,
        finished;

    $('.in_game').show();
    $('.out_game').hide();
    airport.show_screen('airport', '{{ landed_sound }}');

    if (data.finished) {
        finished = new airport.LightBox('#finished_content');
        $('#finished_content a').attr(
                'href', '{% url "game_summary" %}' + '?id=' + data.game);
        finished.show();
    }

    if (data.redirect) {
        window.location.replace(data.redirect);
        return;
    }

    if (data.city) {
        city_image_url = ('{% url "city_image" %}' + encodeURIComponent(data.city) + '/');
        airport.preload_image(city_image_url);
    }

    airport.change_background($('#airport_screen'), city_image_url);
    $('#airportname').html('Welcome to ' + data.city);

    /* update the flights */
    airport.flights_table(data.next_flights);

    // ticket widget
    airport.update_ticket_widget(data.ticket, data.player);
    
    airport.update_panel(data);

    if (data.game_state === 'Paused') {
        airport.paused = airport.paused || new airport.LightBox('#lightbox_content');
        airport.paused.show();
    } else if (airport.paused) {
        airport.paused.hide();
        airport.paused = null;
    }
};


airport.update_games_menu = function (games)
{
    var game,
        $tbody = $('#games_widget tbody'),
        template = $('#game_row_template').html();

    $tbody.empty();
    for (var i = 0; i < games.length; i++) {
        game = games[i];
        if (i % 2 === 0) {
            game.odd_or_even = 'even';
        } else {
            game.odd_or_even = 'odd';
        }

        $tbody.append(Mustache.render(template, game));
    }

    $('td.play_game input').click(airport.select_game);

    if (games.length === 0) {
        $tbody.append('<tr><td id="no_games" colspan="7">&nbsp;No games... start a new one!</td></tr>');
    }
};


airport.show_screen = function (screen, sound)
{
    var id = screen + '_screen';

    if (airport.screen === screen) {
        return;
    }

    $('.screen').each(function (i, screen_div) {
        if (screen_div.id !== id && $(screen_div).is(':visible')) {
            $(screen_div).slideUp(500);
        }
    });
    
    if (sound !== undefined) {
        airport.play(sound);
    }
    $('#' + id).slideDown(500);
    airport.screen = screen;
};


/* Callback when a button is clicked in the "Active Games" menu */
airport.select_game = function (e)
{
    var game_id = $(this).val();

    $('*').css('cursor', 'wait');
    $.ajax({
        type: 'POST',
        url: "{% url 'airport.views.games_join' %}", 
        data: {id: game_id},
        success: airport.refresh_ui,
        complete: function () {$('*').css('cursor', 'auto');}
    });
};


/* pre-load an image into memory */
airport.preload_image = function (url)
{
    if (airport.background_image.url != url) {
        airport.background_image.src = url;
        airport.background_image.url = url;
    }
};


/* Change the background image of an $elem */
airport.change_background = function ($elem, src)
{
    var url = 'url(' + src + ')',
        visible = $elem.is(':visible'),
        zindex = $elem.zIndex();

    if ($elem.data('background') === src) return;

    /* if the element isn't visible then some browsers (Chrome at least), won't
     * update the background until it actually becomes visible, causing a delay
     * This is undesirable
     */
    if (! visible) {
        $elem.zIndex(-1000);
        $elem.show();
    }
    $elem.css('background-image', url);
    $elem.data('background', src);
    if (! visible) {
        $elem.hide();
        $elem.zIndex(zindex);
    }
};


/* update the outgoing flights table at an airport */
airport.flights_table = function (flights)
{
    var s = '',
        i,
        flight,
        num_flights = flights.length,
        template = $('#schedule_template').html(),
        schedule = $('#flights');

    schedule.empty();
    for (i = 0; i<num_flights; i++) {
        flight = flights[i];
        if (i%2) {
            flight["odd_or_even"] = "odd";
        }
        else {
            flight["odd_or_even"] = "even";
        }
        s = Mustache.render(template, flight);
        schedule.append(s);
    }

    /* we prefer at least 10 rows */
    for (; i < 10; i++) {
        if (i % 2) {
            odd_or_even = "odd";
        }
        else {
            odd_or_even = "even";
        }
        s = Mustache.render(template, {"odd_or_even": odd_or_even});
        schedule.append(s);
    }

    $('.buy > input').click(function() {
        var name = $(this).attr('name');
        var ticket_no = name.substring(4);
        $('#selected').val(ticket_no);
    });
};


airport.update_ticket_widget = function (ticket, player)
{
    "use strict";
    var widget = $('#ticket_widget');
    
    if (!ticket) {
        if (widget.is(':visible')) {
            widget.hide('drop', { direction: 'down' }, 100);
        }
        return;
    }
    
    $('#ticket_name').html(player.toUpperCase());
    $('#ticket_status').html(ticket.status.toUpperCase());
    $('#ticket_no').html(ticket.number);
    $('#ticket_origin').html(ticket.origin.code.toUpperCase());
    $('#ticket_dest').html(ticket.destination.code.toUpperCase());
    $('#ticket_depart').html(ticket.depart_time.toUpperCase());
    $('#ticket_arrive').html(ticket.arrival_time.toUpperCase());
    widget.fadeIn();

    if (ticket.number != airport.last_ticket) {
        airport.play('{{ ticket_sound }}');
    }
    airport.last_ticket = ticket.number;
};


airport.update_goals = function (goals)
{
    "use strict";
    var s = '',
        new_goal,
        current_goal_flagged = false,
        goal;

    for (var i = 0; i < goals.length; i++) {
        goal = goals[i];
        if (goal[1]) {
            s = s + '<li class="goal_city achieved">' + goal[0] + '</li>\n';
        }
        else {
            if (!current_goal_flagged) {
                s = s +'<li class="goal_city current">' + goal[0] + '</li>\n';
                current_goal_flagged = true;
                if (airport.current_goal != goal[0]) {
                    new_goal = true;
                    airport.current_goal = goal[0];
                }
                else {
                    new_goal = false;
                }
            }
            else { 
                s = s +'<li class="goal_city">' + goal[0] + '</li>\n';
            }
        }
    }
    $('#goals').html(s);
    if (new_goal) {
        $('li.current').effect("pulsate", {times: 4}, 700);
    }
};


/*
 * Update the stats widget showing all players and how many goals they
 * have met
 */
airport.update_stats = function (stats)
{
    "use strict";
    var s = '',
        widget = $('#stats_box');
    
    for (var i = 0; i < stats.length; i++) {
        s = s + '<tr><td>' + stats[i][0] + '</td><td>';
        for (var j = 0; j < stats[i][1]; j++) {
            s = s + '<img src="' + airport.goldstar + '" />';
        }
    }
    widget.html(s);
    return widget;
};


/* callback for when a buy ticket button has been clicked */
airport.buy_ticket = function (e)
{
    "use strict";
    var form = $('#frm'),
        selected = form.find('#selected').val();

    e.preventDefault();
    $('input[name="buy_'+selected+'"]').attr('disabled', true);
    $('*').css('cursor', 'wait');
    airport.play('{{ button_click }}');
    $.ajax({
        type: 'POST',
        success: function (data) {airport.refresh_ui(data);},
        complete: function () {$('*').css('cursor', 'auto');},
        data: form.serialize(),
        url: "{% url 'info' %}"
    });
};


/* update the panel widgets */
airport.update_panel = function (data)
{
    "use strict";

    // clock(s)
    $('.time').html(data.time);

    // goals
    airport.update_goals(data.goals);

    // stats
    airport.update_stats(data.stats);
};



/* Callback for the create_game form */
airport.create_game = function (e)
{
    "use strict";
    var $form = $(this);

    e.preventDefault();
    airport.play('{{ button_click }}');

    $.post($form.prop('action'), $form.serialize(), airport.refresh_ui);
};


/* Callback for update the goals slider */
airport.update_goals_slider = function ()
{
    "use strict";
    var goals = $('#goals_range').val();
    $('#goals_count').html(goals);
};


/* Callback for update the airports slider */
airport.update_airports_slider = function ()
{
    "use strict";
    var airports = $('#airports_range').val();
    $('#airports_count').html(airports);
};


/* Callback that posts when a user clicks on a link */
airport.post_link = function (e)
{
    e.preventDefault();
    var href = $(this).prop('href');

    $.ajax({
        type: 'POST',
        url: href,
        success: airport.refresh_ui
    });
};


/* Callback to periodically update the games screen */
airport.games_screen_interval_cb = function ()
{
    if (airport.screen !== 'games') {
        return;
    }

    $.ajax({
        type: 'GET',
        success: airport.refresh_ui,
        url: '{% url "info" %}'
    });
};


/* play sound specified by url */
airport.play = function (url) {
    "use strict";
    if (window['Audio'] === undefined) {
        return null;
    }
    var snd = new Audio(url);
    snd.play();
    return snd;
};


airport.websocket_connect = function (page) {
    "use strict";
    var socket = new WebSocket("{{ websocket_url }}");

    socket.onopen = function () {
        this.send(JSON.stringify({type: 'page', data: page}));
    };

    socket.onmessage = function (message) {
        message = JSON.parse(message.data);

        if (airport.websocket_handlers.hasOwnProperty(message.type)) {
            airport.websocket_handlers[message.type](message.data);
        }
    };
};
