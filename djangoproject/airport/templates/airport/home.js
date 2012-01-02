var goldstar = "{{ gold_star }}",
    last_ticket = null,
    last_goal = null,
    new_goal = false;

function refresh_ui(data) {
    var ticket;
    var goal;
    var s;
    var current_goal_flagged = false;

    if (data['redirect']) {
        window.location.replace(data['redirect']);
        return;
    }

    if (data['notify']) {
        airport.notify(data['notify']);
    }

    $('#game').html(data['game']);
    $('#clock span').html(data['time']);

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

        if ($('#airport_widget').is(':visible')) {
            $('#airport_widget').hide();
            airport.play('{{ takeoff_sound }}');
        }
        $('#airplane_widget').show();
    }
    else {
        $('#airplane_widget').hide();

        $('#flights').load('{% url airport.views.flights game.id %}');

        $('#airportname').html('Welcome to ' + data['airport'] + ' Airport');
        if (!$('#airport_widget').is(':visible')) {
            $('#airport_widget').show('drop', { direction: 'up' }, 500);
            airport.play('{{ landed_sound }}');
        }
    }

    ticket = data['ticket'];
    if (ticket) {
        $('#ticket_name').html('<span class="ticket_label">NAME</span> '
                + data['player'].toUpperCase());
        $('#ticket_status').html('<span class="ticket_label">STATUS</span> '
                + ticket['status'].toUpperCase());
        $('#ticket_no').html('<span class="ticket_label">FLIGHT</span> '
                + ticket['number']);
        $('#ticket_origin').html('<span class="ticket_label">FROM</span> '
                + ticket['origin'].toUpperCase());
        $('#ticket_dest').html('<span class="ticket_label">TO</span> '
                + ticket['destination'].toUpperCase());
        $('#ticket_depart').html('<span class="ticket_label">DEPART</span> '
                + ticket['depart_time'].toUpperCase());
        $('#ticket_arrive').html('<span class="ticket_label">ARRIVE</span> '
                + ticket['arrival_time'].toUpperCase());
        $('#ticket_widget').fadeIn();

        if (ticket['number'] != last_ticket) {
            airport.play('{{ ticket_sound }}');
        }
        last_ticket = ticket['number'];
    } 
    else if ($('#ticket_widget').is(':visible')) {
        $('#ticket_widget').hide('drop', { direction: 'down' }, 500);
    }
        
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
    s = '';
    for (var i=0; i<data['stats'].length; i++) {
        s = s + '<tr><td>' + data['stats'][i][0] + '</td><td>';
        for (var j=0; j<data['stats'][i][1]; j++) {
            s = s + '<img src="' + goldstar + '" />';
        }
    }
    $('#stats_box').html(s);
}

function refresh_cb(data, textStatus, jqXHR) {
    refresh_ui(data);
    setTimeout(function() {
        $.ajax({
            url: "{% url info %}", 
            success: refresh_cb, 
            dataType: "json"
        })},
        5000);
}

function buy_ticket() {
    /* callback for when a buy ticket button has been clicked */
    $.ajax({
        type: 'POST',
        success: function(data) { refresh_ui(data);},
        data: $('#frm').serialize(),
        url: "{% url info %}"
    });
    return false;
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

function main() {
    /* document.ready function */
    $('#airplane_widget').hide();
    $('#notification_permission').hide();
    show_notifications_widget();

    $('#goal_widget').memdraggable();
    $('#stats_widget').memdraggable();
    $('#flight_schedule').memdraggable({handle: '#game'});
    $('#ticket_widget').memdraggable();
    $('#message_widget').memdraggable();
    $('#clock').memdraggable();
    $('#notepad').memdraggable({handle: '.header'}).memresizable();

    $('#frm').submit(buy_ticket);
    $('#permit_notify').click(permit_notifications_cb);

    airport.messages('#message_box');
    $.ajax({
        url: "{% url info %}",
        success: refresh_cb,
        dataType: "json"
    });

}

$(document).ready(main);
