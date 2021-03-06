/*
 * Common functions for the Airport app
*/
(function( $ ) {
    $.fn.memdraggable = function(options) {
        var id = this.attr('id');
        var coords = this.offset();
        var split, x, y;
        var window_width, window_height;

        this.draggable(options);

        this.bind('dragstop', function() {
            var coords = $(this).offset();
            var window_width, window_height;

            window_width = $(window).width();
            window_height = document.documentElement.clientHeight;
            /* $(window).height() broken in webkit see:
             * http://forum.jquery.com/topic/window-height-in-safari-is-incorrect
             */

            /* ensure we're within bounds */
            if (coords.top < 0) {
                coords.top = 0;
            }
            if (coords.top > window_height) {
                coords.top = window_height;
            }
            if (coords.left < 0) {
                coords.left = 0;
            }
            if (coords.left > window_width) {
                coords.left = window_width;
            }

            $(this).css('opacity', $(this).data('opacity'));
            $.cookie(
                id + '_pos', 
                coords.left + ':' + coords.top, { expires: 30 }
            );
        });

        this.bind('dragstart', function() {
            var orig_opacity = $(this).css('opacity');
            $(this).data('opacity', orig_opacity);
            $(this).css('opacity', 0.7);
            $('.ui-draggable').css('z-index', 0);
            $(this).css('z-index', 1);
        });

        /* load position */
        coords = $.cookie(id + '_pos');
        window_width = $(window).width();
        window_height = document.documentElement.clientHeight;
        if (coords != null) {
            split = coords.split(':', 2);
            x = split[0];
            y = split[1];

            window_width = $(window).width();
            window_height = document.documentElement.clientHeight;
            /* $(window).height() broken in webkit see:
             * http://forum.jquery.com/topic/window-height-in-safari-is-incorrect
             */

            /* ensure we're within bounds */
            if (y < 1) {
                y = 1;
            }
            if (y > window_height) {
                y = window_height;
            }
            if (x < 1) {
                x = 1;
            }
            if (x > window_width) {
                x = window_width;
            }
            this.offset({ left: x, top: y});
        }
    return this;
    };
})( jQuery );

(function( $ ) {
    $.fn.memresizable = function(options) {
        var id = this.attr('id'),
            width = this.width(),
            height = this.height(),
            split,
            size;

        this.resizable(options);

        this.bind('resizestop', function() {
            var width = $(this).width(),
                height = $(this).height();

            $(this).css('opacity', $(this).data('opacity'));
            $.cookie(
                id + '_size', 
                width + 'x' + height, { expires: 30 }
            );
        });

        this.bind('resizestart', function() {
            var orig_opacity = $(this).css('opacity');
            $(this).data('opacity', orig_opacity);
            $(this).css('opacity', 0.7);
        });

        /* load size  */
        size = $.cookie(id + '_size');
        if (size != null) {
            split = size.split('x', 2);
            width = split[0];
            height = split[1];

            this.width(width);
            this.height(height);
        }
    return this;
    };
})( jQuery );

jQuery.fn.center = function () {
    this.css("position","absolute");
    this.css("top", (($(window).height() - this.outerHeight()) / 2) + $(window).scrollTop() + "px");
    this.css("left", (($(window).width() - this.outerWidth()) / 2) + $(window).scrollLeft() + "px");
    return this;
}
