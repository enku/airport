var airport = window.airport || {};

airport.websocket_handlers = {
    message: function (data) {
        var icon = airport.message_icons[data.type],
            sound = airport.message_sounds[data.type],
            html = Mustache.to_html(
                $('#message_template').html(), 
                {message: data, icon: icon, sound: sound}
        );
        $('#message_box ul').append(html);
    },

    info: function (data) {
        airport.refresh_ui(data);
    },

    games_info: function (data) {
        airport.update_games_menu(data.games);
    },

    join_game: function () {
        window.location.replace('{% url "main" %}');
    },

    quit_game: function(data) {
	data.current_game = null;
	data.current_state = 'open';
        airport.refresh_ui(data);
    }
};
