function update_messages(messages) {
    for(var i=0; i<messages.length; i++) {
        message = messages[i];
        if ($('.message:[data-id=' + message['id'] + ']').length == 0) {
            $('#message_box').append(
                '<div class="message" data-id="' + message['id'] + '">' 
                + '<img src="' + inbox + '" />&nbsp;' + message['text'] 
                + '</div>\n');
        }
    }
    $('#message_widget').scrollTo('max', {
        axis: 'y',
        duration: 500,
        margin: true
        });
}
