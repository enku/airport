var goldstar = "{{ gold_star }}";
var inbox = "{{ inbox_icon }}";
var notify_timeout = 20000 /* milliseconds */

function notify(message) {
    /* send a desktop notification, if allowed */
    if (!window.webkitNotifications) {
        return;
    }
    if (window.webkitNotifications.checkPermission() == 0) {
        var notification = window.webkitNotifications.createNotification(
            '{{ notification_icon }}', 'Airport', message);
        notification.show();
        setTimeout(function() { notification.cancel();}, notify_timeout);
    }
}

function refresh_ui(data) {
    var odd_or_even;
    var ticket;
    var goal;
    var s;

    if (data['redirect']) {
        window.location.replace(data['redirect']);
        return;
    }

    if (data['notify']) {
        notify(data['notify']);
    }

    $('#username').html(data['player']);
    $('#clock span').html(data['time']);

    if (data['in_flight']) {
        $('#flight_status').html(data['player']
                + ' flying Flight '
                + data['ticket']['number']
                + ' to '
                + data['ticket']['destination']
                + ' arriving at <span class="time">'
                + data['ticket']['arrival_time']
                + '&nbsp;<span class="fsb">NO SMOKING</span>'
                + '&nbsp;<span class="fsb">FASTEN SEATBELT WHILE SEATED</span>'
                + '</span>');

        $('#airport_widget').hide();
        $('#airplane_widget').show();
    }
    else {
        $('#airplane_widget').hide();

        $('#flights').load('{% url airport.views.flights %}');


        $('#airport_widget').show();
        $('#airportname').html('Welcome to ' + data['airport'] + ' Airport');
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
    } 
    else if ($('#ticket_widget').is(':visible')) {
        $('#ticket_widget').hide('drop', { direction: 'down' }, 500);
    }
        
    // goals
    $('#goals').html('');
    for (var i=0; i<data['goals'].length; i++) {
        goal = data['goals'][i];
        if (goal[1]) {
            $('#goals').append('<div class="goal_city">' + goal[0] + ' <img src="' + goldstar + '" /></div>\n');
        }
        else {
            $('#goals').append('<div class="goal_city">' + goal[0] + '</div>\n');
        }
    }

    // messages
    update_messages(data['messages']);

    // stats
    s = ''
    for (var i=0; i<data['stats'].length; i++) {
        s = s + '<div>';
        s = s + data['stats'][i][0] + ' ';
        for (var j=0; j<data['stats'][i][1]; j++) {
            s = s + '<img style="text-align: right" src="' + goldstar + '" />';
        }
        s = s + '</div>\n';
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
    $('#flight_schedule').memdraggable();
    $('#ticket_widget').memdraggable();
    $('#message_widget').memdraggable();
    $('#clock').memdraggable();

    $('#frm').submit(buy_ticket);
    $('#permit_notify').click(permit_notifications_cb);

    $.ajax({
        url: "{% url info %}",
        success: refresh_cb,
        dataType: "json"
    });

}

$(document).ready(main);
