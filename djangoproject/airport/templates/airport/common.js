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
            $(this).css('opacity', $(this).data('opacity'));
            $(this).css('z-index', 0);
            $.cookie(
                id + '_pos', 
                coords.left + ':' + coords.top, { expires: 30 }
            );
        });

        this.bind('dragstart', function() {
            var orig_opacity = $(this).css('opacity');
            $(this).data('opacity', orig_opacity);
            $(this).css('opacity', 0.7);
            $(this).css('z-index', 999);
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
