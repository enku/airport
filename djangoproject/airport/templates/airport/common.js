/*
 * Common functions for the Airport app
*/
var notify_timeout = 20000 /* milliseconds */
var notification = null;

function notify(message) {
    /* send a desktop notification, if allowed */
    if (!window.webkitNotifications) {
        return;
    }
    if (window.webkitNotifications.checkPermission() == 0) {
        notification = window.webkitNotifications.createNotification(
            '{{ notification_icon }}', 'Airport', message);
        notification.show();
        setTimeout(function() { notification.cancel();}, notify_timeout);
    }
}

function play(url) {
    /* play sound specified by url */
    if (window['Audio'] == undefined) {
        return null;
    }
    var snd = new Audio(url);
    snd.play();
    return snd;
}

function LightBox(bg, content) {

    this.show = function() {
        if (!this.visible) {
            this.bg.fadeIn();
            this.content.css('display', 'inline-block');
            this.content.center();
            this.content.fadeIn();
            this.visible = true;
        }
    }

    this.hide = function() {
        if (this.visible) {
            this.bg.fadeOut();
            this.content.fadeOut();
            this.visible = false;
        }
    }

    this.bg = $(bg);
    this.content = $(content);
    this.visible = false;

    this.bg.addClass('lightbox');
    this.content.addClass('lightbox_content')
}

(function( $ ) {
    $.fn.memdraggable = function() {
        var id = this.attr('id');
        var coords = this.offset();
        var split, x, y;
        var window_width, window_height;

        this.draggable();

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
    };
})( jQuery );

jQuery.fn.center = function () {
    this.css("position","absolute");
    this.css("top", (($(window).height() - this.outerHeight()) / 2) + $(window).scrollTop() + "px");
    this.css("left", (($(window).width() - this.outerWidth()) / 2) + $(window).scrollLeft() + "px");
    return this;
}
