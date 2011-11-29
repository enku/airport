var inbox = "http://starsvet.com/templates/tmpl_ae4/images_ae4/write_message.gif";

function update_games_list(data) {
    /* update the games list widget */
    var s = '';
    var game;

    for (var i=0; i<data['games'].length; i++) {
        game = data['games'][i];
        s = s + ('<tr><td><a href="{% url games_join %}' + game['id'] + '">' + game['id'] + '</a></td>' 
                + '<td>' +  game['players__count'] + '</td>'
                + '<td>' + game['goals__count'] + '</td></tr>\n');
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
    $('#message_box').html('');
    for(var i=0; i<data['messages'].length; i++) {
        message = data['messages'][i]
        $('#message_box').append(
            '<div class="message">' + '<img src="' + inbox + '" />&nbsp;' + message + '</div>\n');
        // scroll to bottom
        $("#message_widget").prop({
            scrollTop: $("#message_widget").prop("scrollHeight") });
    }
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
    if (goals > 1) {
        $('#goals_count').html(goals + ' Goals');
    }
    else {
        $('#goals_count').html('1 Goal');
    }
}

function create_game() {
    var goals = $('#goals_range').val();
    window.location.replace('{% url games_create %}' + goals );
}

function main() {
    /* document.ready function */
    $('#goals_range').change(update_goals);
    $('#start_game').click(create_game);
    $.ajax({
        url: "{% url games_info %}",
        success: refresh_cb,
        dataType: "json"
    });
}

$(document).ready(main);
