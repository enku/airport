/*
 * Common functions for the Airport app
*/

(function( $ ) {
    $.fn.memdraggable = function() {
        var id = this.attr('id');
        var coords = this.offset();
        var split, x, y;

        this.draggable();
        this.bind('dragstop', function() {
            var coords = $(this).offset();
            $.cookie(
                id + '_pos', 
                coords.left + ':' + coords.top, { expires: 30 }
            );
        });

        /* load position */
        coords = $.cookie(id + '_pos');
        if (coords != null) {
            split = coords.split(':', 2);
            x = split[0];
            y = split[1];
            this.offset({ left: x, top: y});
        }
    };
})( jQuery );
