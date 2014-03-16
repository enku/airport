var airport = window.airport || {};


airport.message_sounds = {
    DEFAULT: "{{ message_DEFAULT_sound }}",
    ERROR: "{{ message_ERROR_sound }}",
    GAMEOVER: "{{ message_GAMEOVER_sound }}",
    GOAL: "{{ message_GOAL_sound }}",
    MONKEYWRENCH: "{{ message_MONKEYWRENCH_sound }}",
    NEWGAME: "{{ message_NEWGAME_sound }}",
    WINNER: "{{ message_WINNER_sound }}"
}


airport.message_icons = {
    DEFAULT: "{{ message_DEFAULT_icon }}",
    MONKEYWRENCH: "{{ message_MONKEYWRENCH_icon }}",
    ERROR: "{{ message_ERROR_icon }}",
    PLAYERACTION: "{{ message_PLAYERACTION_icon }}",
    GOAL: "{{ message_GOAL_icon }}",
    NEWGAME: "{{ message_NEWGAME_icon }}",
    WINNER: "{{ message_WINNER_icon }}"
}


airport.messages = function(widget) {

    var update = function() {
        if (initial) {
            $.get('{% url "messages" %}', {last: last_message, old: 'true'}, 
                  append);
            initial = false;
            return;
        }
        $.get('{% url "messages" %}', {last: last_message}, append);
    }

    var append = function(data) {
        if (data !== undefined) {
            widget.append(data);
            last_message = widget.data('last_message');
        }
    }

    var last_message = '0';
    var widget = $(widget);
    var initial = true;

    update();
    return this;
}
