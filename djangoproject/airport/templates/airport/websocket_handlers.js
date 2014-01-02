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
        refresh_ui(data);
    },

    games_info: function (data) {
        refresh_ui(data);
    }
};
