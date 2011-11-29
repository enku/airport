var goldstar = "http://njwltech.wikispaces.com/file/view/gold_star.png/35350229/gold_star.png";
var inbox = "http://starsvet.com/templates/tmpl_ae4/images_ae4/write_message.gif";
var widgets = new Array(
    'goal_widget',
    'stats_widget',
    'flight_schedule',
    'ticket_widget',
    'message_widget',
    'clock'
);


function refresh_ui(data) {
    var odd_or_even;
    var ticket;
    var goal;
    var message;
    var s

    if (data['redirect']) {
        window.location.replace(data['redirect']);
        return;
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
                + '</span>');

        $('#airport_widget').hide();
        $('#airplane_widget').show();
    }
    else {
        $('#airplane_widget').hide();
        $('#airport_widget').show();
        $('#airportname').html('Welcome to ' + data['airport'] + ' Airport');
    }

    /* iterate over the schedules */
    var s = '';
    for(var i=0; i<data['next_flights'].length; i++) {
        if (i%2) {
            odd_or_even = "odd";
        }
        else {
            odd_or_even = "even";
        }
        s = s + (
            '<tr class="schedule ' + odd_or_even + '" id="flight_"' + data['next_flights'][i]['number'] + '>\n'
            + '<td>' + data['next_flights'][i]['destination'] + '</td>\n'
            + '<td class="flightno">' + data['next_flights'][i]['number'] + '</td>\n'
            + '<td>' + data['next_flights'][i]['depart_time'] + '</td>\n'
            + '<td>' + data['next_flights'][i]['arrival_time'] + '</td>\n'
            + '<td>' + data['next_flights'][i]['status'] + '</td>\n');

        if (data['next_flights'][i]['buyable']) {
            s = s + (
                '<td class="buy"><input type="submit" value="Buy" name="buy_' 
                + data['next_flights'][i]['number'] 
                + '" /></td></tr>\n');
        }
        else {
            s = s + (
                '<td class="buy"><input disabled="disabled" type="submit" value="Buy" name="buy_' 
                + data['next_flights'][i]['number'] 
                + '" /></td></tr>\n');
        }
    };
    $('#flights').html(s);

    $('input').click(function() {
            var name = $(this).attr('name');
            var ticket_no = name.substring(4);
            $('#selected').val(ticket_no);
    });

    ticket = data['ticket'];
    if (ticket) {
        $('#ticket_name').html('<span class="ticket_label">NAME</span> '
                + data['player'].toUpperCase());
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
    else {
        $('#ticket_widget').fadeOut();
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
    $('#message_box').html('');
    for(var i=0; i<data['messages'].length; i++) {
        message = data['messages'][i]
        $('#message_box').append(
            '<div class="message">' + '<img src="' + inbox + '" />&nbsp;' + message + '</div>\n');
        // scroll to bottom
        $("#message_widget").prop({
            scrollTop: $("#message_widget").prop("scrollHeight") });
    }

    // stats
    s = ''
    for (var i=0; i<data['stats'].length; i++) {
        s = s + '<div>';
        s = s + data['stats'][i][0] + ' ';
        for (var j=0; j<data['stats'][i][1]; j++) {
            s = s + '<img style="align: right" src="' + goldstar + '" />';
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

function save_position() {
    var coords = $(this).offset();
    var id = $(this).attr('id');
    $.cookie(id + '_pos', coords.left + ',' + coords.top);
}

function load_position(widget) {
    var coords = $.cookie(widget + '_pos');
    var split, x, y;
    if (coords != null) {
        split = coords.split(',', 2);
        x = split[0];
        y = split[1];
        $('#' + widget).offset({ left: x, top: y});
    }
}

function main() {
    /* document.ready function */
    $('#airplane_widget').hide();
    $('#airplane_widget').bind('dragstop', save_position);

    for (var i=0; i<widgets.length; i++) {
        $('#' + widgets[i]).draggable();
        $('#' + widgets[i]).mouseover(function() {$(this).css('cursor', 'move');});
        $('#' + widgets[i]).bind('dragstop', save_position);
        load_position(widgets[i]);
    }

    $('#frm').submit(buy_ticket);

    $.ajax({
        url: "{% url info %}",
        success: refresh_cb,
        dataType: "json"
    });

}

$(document).ready(main);
