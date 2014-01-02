var goldstar = "{{ gold_star }}",
    background_image = new Image(25, 25),
    last_ticket = null,
    last_goal = null,
    timeout = null,
    lightbox,
    new_goal = false;

function flights_table(flights) {
    var s = '',
        i,
        flight,
        num_flights = flights.length,
        template = $('#schedule_template').html(),
        schedule = $('#flights');

    schedule.empty();
    for (i=0; i<num_flights; i++) {
        flight = flights[i];
        if (i%2) {
            flight["odd_or_even"] = "odd";
        }
        else {
            flight["odd_or_even"] = "even";
        }
        s = Mustache.to_html(template, flight);
        schedule.append(s);
    }

    /* we prefer at least 10 rows */
    for (i=i; i<10; i++) {
        if (i%2) {
            odd_or_even = "odd";
        }
        else {
            odd_or_even = "even";
        }
        s = Mustache.to_html(template, {"odd_or_even": odd_or_even});
        schedule.append(s);
    }

    $('input').click(function() {
        var name = $(this).attr('name');
        var ticket_no = name.substring(4);
        $('#selected').val(ticket_no);
    });
}

function update_ticket_widget(ticket, player) {
    var widget = $('#ticket_widget');
    
    if (!ticket) {
        if (widget.is(':visible')) {
            widget.hide('drop', { direction: 'down' }, 100);
        }
        return;
    }
    
    $('#ticket_name').html(player.toUpperCase());
    $('#ticket_status').html(ticket['status'].toUpperCase());
    $('#ticket_no').html(ticket['number']);
    $('#ticket_origin').html(ticket['origin'].toUpperCase());
    $('#ticket_dest').html(ticket['destination'].toUpperCase());
    $('#ticket_depart').html(ticket['depart_time'].toUpperCase());
    $('#ticket_arrive').html(ticket['arrival_time'].toUpperCase());
    widget.fadeIn();

    if (ticket['number'] != last_ticket) {
        airport.play('{{ ticket_sound }}');
    }
    last_ticket = ticket['number'];
}

/*
 * Update the stats widget showing all players and how many goals they
 * have met
 */
function update_stats(stats) {
    var s = '',
        widget = $('#stats_box');
    
    for (var i=0; i<stats.length; i++) {
        s = s + '<tr><td>' + stats[i][0] + '</td><td>';
        for (var j=0; j<stats[i][1]; j++) {
            s = s + '<img src="' + goldstar + '" />';
        }
    }
    widget.html(s);
    return widget;
}

function flip_background(src) {
    var body = $('body'),
        elem;

    if (body.data('background') === src) return;

    elem = $('<div></div>').hide();
    elem.width($(window).width());
    elem.height($(window).height());
    elem.css('background-image', body.css('background-image'));
    elem.css('background-size', 'cover');
    elem.css('background-repeat', 'repeat-none');
    elem.css('position', 'absolute');
    elem.css('left', '0');
    elem.css('top', '0');
    elem.css('z-index', '-1');
    body.prepend(elem);
    elem.show();


    body.data('background', src);
    body.css('background-image', 'url(' + src + ')');
    elem.fadeOut(1500, function () {
        elem.remove();
    });
    return;
}

function preload_image(url) {
    if (background_image.src != url)
        background_image.src = url;
}

function refresh_ui(data) {
    var ticket,
        player = data['player'],
        goal,
        s,
        city_image_url,
        current_goal_flagged = false;

    if (data['redirect']) {
        if (data['finished']) {
            $('#finished_content a').attr('href', data['redirect']);
            finished.show();
        }
        else {
            window.location.replace(data['redirect']);
            return;
        }
    }

    if (data['notify']) {
        airport.notify(data['notify']);
    }

    if (data['city']) {
        city_image_url = ('{% url "city_image" %}' 
                          + encodeURIComponent(data['city']) + '/');
        preload_image(city_image_url);
    }

    $('.time').html(data['time']);

    if (data['in_flight']) {
        $('#flight_status').html('&nbsp;Flight '
                + data['ticket']['number']
                + ' to '
                + data['ticket']['destination']
                + ' arriving at <span class="time">'
                + data['ticket']['arrival_time']
                + '&nbsp;<span class="fsb">NO SMOKING</span>'
                + '&nbsp;<span class="fsb">FASTEN SEATBELT WHILE SEATED</span>'
                + '</span>');

        /* update progress bar */
        $( "#progress" ).progressbar("value", data['percentage'] );

        if ($('#airport_widget').is(':visible')) {
            $('#airport_widget').hide();
            airport.play('{{ takeoff_sound }}');
        }
        $('#airplane_widget').show();
        flip_background('{{ background_image }}');
    }
    else {
        $('#airplane_widget').hide();

        flip_background(city_image_url);

        $('#airportname').html('Welcome to ' + data['airport'] + ' Airport');

        /* update the flights */
        flights_table(data['next_flights']);

        if (!$('#airport_widget').is(':visible')) {
            $('#airport_widget').show('drop', { direction: 'up' }, 500);
            airport.play('{{ landed_sound }}');
        }
    }

    // ticket widget
    update_ticket_widget(data['ticket'], player);
    
    // goals
    s = '';
    for (var i=0; i<data['goals'].length; i++) {
        goal = data['goals'][i];
        if (goal[1]) {
            s = s + '<li class="goal_city achieved">' + goal[0] + '</li>\n';
        }
        else {
            if (!current_goal_flagged) {
                s = s +'<li class="goal_city current">' + goal[0] + '</li>\n';
                current_goal_flagged = true;
                if (last_goal != goal[0]) {
                    new_goal = true;
                    last_goal = goal[0];
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
        $('li.current').effect("pulsate", { times:4 }, 700);
    }

    // stats
    update_stats(data['stats']);

    if (data['game_state'] == 'Paused') lightbox.show();
    else lightbox.hide();
}

function buy_ticket(event) {
    /* callback for when a buy ticket button has been clicked */
    event.preventDefault();
    var form = $('#frm'),
        selected = form.find('#selected').val();
    $('input[name="buy_'+selected+'"]').attr('disabled', true);
    airport.play('{{ button_click }}');
    $.ajax({
        type: 'POST',
        success: function(data) { refresh_ui(data);},
        data: form.serialize(),
        url: "{% url "info" %}"
    });
}

function show_notifications_widget() {
    /* show the notifications permission checkbox if the browser supports it,
     * but the user has not allowed the permission */
    if (window.webkitNotifications 
        && window.webkitNotifications.checkPermission() != 0) {
        $('#notification_permission').show();
    }
}

function permit_notifications_cb() {
    /* call requestPermissions if the user has clicked on the allow
     * notifications checkbox */
    $('#notification_permission').fadeOut();
    if (window.webkitNotifications) {
        window.webkitNotifications.requestPermission();
    }
}

function pause_game(event) {
    event.preventDefault();
    $.ajax({
        type: 'POST',
        url: "{% url "pause_game" %}?id=" + "{{ game.id }}",
        success: function(data) { refresh_ui(data);}
    });
}

function quit_game(event) {
    event.preventDefault();
    $.ajax({
        type: 'POST',
        url: "{% url "rage_quit" %}?id={{game.id}}",
        success: function(data) { refresh_ui(data);}
    });
}

function main() {
    /* document.ready function */
    $('#airplane_widget').hide();
    $('#notification_permission').hide();
    $('#progress').progressbar({value: 0});
    show_notifications_widget();

    $('#goal_widget').memdraggable();
    $('#stats_widget').memdraggable();
    $('#flight_schedule').memdraggable({handle: '#game'});
    $('#ticket_widget').memdraggable();
    $('#message_widget').memdraggable();
    $('#clock').memdraggable();
    $('#notepad').memdraggable({handle: '.header'}).memresizable();

    $('#frm').submit(buy_ticket);
    $('#pause').click(pause_game);
    $('#resume').click(pause_game);
    $('#ragequit').click(quit_game);
    $('#permit_notify').click(permit_notifications_cb);

    airport.messages('#message_box');
    airport.websocket_connect('home');
    lightbox = new airport.LightBox('#lightbox_content');
    finished = new airport.LightBox('#finished_content');
    $.ajax({
        type: 'GET',
        success: function(data) { refresh_ui(data);},
        url: '{% url "info" %}'
    });
}

$(document).ready(main);
