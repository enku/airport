var inbox = "{{ inbox_icon }}";

function update_games_list(data) {
    /* update the games list widget */
    var s = '';
    var game;

    for (var i=0; i<data['games'].length; i++) {
        game = data['games'][i];
        s = s + ('<tr><td><a href="{% url games_join %}' + game['id'] + '">' + game['id'] + '</a></td>' 
                + '<td>' + game['goals'] + '</td><'
                + '<td>' + game['airports'] + '</td>'
                + '<td>' +  game['players'] + '</td>'
                + '<td>' + game['host'] + '</td>'
                + '<td>' + game['status'] + '</td>'
                + '<td>' + game['created'] + '</td>'
                + '</tr>\n');
    }
    $('#games_widget tbody').html(s);
}

function join_game_link(data) {
    if (data['current_game'] && !data['finished_current']) {
        $('#start_game').attr('href', '{% url home %}');
        $('#start_game').html('Play game ' + data['current_game'] 
                + ' (current game)');
    }
}

function refresh_ui(data) {
    update_games_list(data);
    join_game_link(data);

    if (data['redirect']) {
        window.location.replace(data['redirect']);
        return;
    }

    // messages
    update_messages(data['messages']);
}

function refresh_cb(data, textStatus, jqXHR) {
    refresh_ui(data);
    setTimeout(function() {
        $.ajax({
            url: "{% url games_info %}", 
            success: refresh_cb, 
            dataType: "json"
        })},
        5000);
}

function update_goals() {
    var goals = $('#goals_range').val();
    $('#goals_count').html(goals);
}

function update_airports() {
    var airports = $('#airports_range').val();
    $('#airports_count').html(airports);
}
function create_game() {
    var goals = $('#goals_range').val();
    window.location.replace('{% url games_create %}' + goals );
}

function main() {
    /* document.ready function */
    $('#goals_range').change(update_goals);
    $('#airports_range').change(update_airports);
    $('#start_game').click(create_game);
    $('#my_stats_widget').load('{% url airport.views.games_stats %}');

    /* widgets that are draggable and remember their positions */
    $('#my_stats_widget').memdraggable();
    $('#games_widget').memdraggable();
    $('#create_widget').memdraggable();
    $('#message_widget').memdraggable();

    $.ajax({
        url: "{% url games_info %}",
        success: refresh_cb,
        dataType: "json"
    });
}

$(document).ready(main);
