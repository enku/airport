function supports_placeholder() {
    var i = document.createElement('input');
    return 'placeholder' in i;
}

function main() {
    if (! supports_placeholder()) {
        $('label').show();
    }
    else {
        $('label').each(function() {
            var input = $(this).attr('for');
            var placeholder = $(this).html();
            $('#' + input).attr('placeholder', placeholder);
        });
    }
}

$(document).ready(main);
