var airport = window.airport || {};

airport.messages = function(widget) {

    this.append = function(data) {
        if (data != '') {
            widget.append(data);
            last_message = widget.data('last_message');
        }
        setTimeout(this.update, 5000);
    }

    this.update = function() {
        if (initial) {
            $.get('{% url messages %}', {last: last_message, old: 'true'}, 
                  this.append);
            initial = false;
            return;
        }
        $.get('{% url messages %}', {last: last_message}, this.append);
    }

    var last_message = '0';
    var widget = $(widget);
    var initial = true;

    this.update();
    return this;
}
