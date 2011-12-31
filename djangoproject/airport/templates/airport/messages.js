function messages(widget) {

    this.append = function(data) {
        if (data != '') {
            widget.append(data);
            last_message = widget.data('last_message');
        }
        setTimeout(update, 5000);
    }

    this.update = function() {
        if (initial) {
            $.get('{% url messages %}', {last: last_message, old: 'true'}, 
                  append);
            initial = false;
            return;
        }
        $.get('{% url messages %}', {last: last_message}, append);
    }

    var last_message = '0';
    var widget = $(widget);
    var initial = true;

    this.update();
}
