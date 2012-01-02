var lightbox;

function update_games_list(data) {
    /* update the games list widget */
    var s = '',
        game = null;

    for (var i=0; i<data['games'].length; i++) {
        game = data['games'][i];
        s = s + ('<tr><td><a class="games_join" href="{% url games_join %}' + game['id'] + '">' + game['id'] + '</a></td>' 
                + '<td>' + game['goals'] + '</td><'
                + '<td>' + game['airports'] + '</td>'
                + '<td>' + game['players'] + '</td>'
                + '<td>' + game['host'] + '</td>'
                + '<td>' + game['status'] + '</td>'
                + '<td>' + game['created'] + '</td>'
                + '</tr>\n');
    }
    $('#games_widget tbody').html(s);
    $('.games_join').click(join_game_cb);
}

function join_game_link(data) {
    if (data['current_game'] && !data['finished_current']) {
        $('#start_game').attr('href', '{% url home %}');
        $('#start_game').html('Play game ' + data['current_game'] 
                + ' (current game)');
    }
}

function refresh_ui(data) {
    if ('redirect' in data) {
        notify('The game has begun');
        window.location.replace(data['redirect']);
        return;
    }

    update_games_list(data);
    join_game_link(data);
    
    if (data['current_state'] == 'hosting') {
        hide_create_widget();
        lightbox.content.html('<a href="{% url home %}"><img src="{{ inflight_image }}"><div>Start Game ' + data['current_game'] + '</div></a>');
        lightbox.show();
    } 
    else if (data['current_state'] == 'waiting') {
        hide_create_widget();
        lightbox.content.html('<img src="{{ inflight_image }}"><div>Waiting for host to start Game ' + data['current_game'] + '</div>');
        lightbox.show();
    } else {
        lightbox.hide();
        show_create_widget();
    }

}

function hide_create_widget() {
    var widget = $('#create_widget');

    if (widget.is(':visible'))
        widget.fadeOut();
}

function show_create_widget() {
    $('#create_widget:hidden').show();
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

/* function called when the create game form is submitted */
function create_form_cb(event) {
    event.preventDefault();

    var form = $('#create_form'), 
        goals = form.find('input[name="goals"]').val(), 
        airports = form.find('input[name="airports"]').val(),
        url = form.attr('action');

    $.post(url, {goals: goals, airports: airports}, refresh_ui);
}

/* function called when user clicks on a join game "button" */
function join_game_cb(event) {
    event.preventDefault();

    var url = $(this).attr('href');
    $.get(url, {}, refresh_ui);
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

    $('#create_form').submit(create_form_cb);

    messages('#message_box');
    lightbox = new LightBox('#lightbox_content');

    $.ajax({
        url: "{% url games_info %}",
        success: refresh_cb,
        dataType: "json"
    });
}

$(document).ready(main);
