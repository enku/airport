var airport = window.airport || {};

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
        if (data != '') {
            widget.append(data);
            last_message = widget.data('last_message');
        }
        setTimeout(update, 5000);
    }

    var last_message = '0';
    var widget = $(widget);
    var initial = true;

    update();
    return this;
}
