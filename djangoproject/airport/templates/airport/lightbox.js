var airport = window.airport || {};

airport.LightBox = function(content) {
    var lb = this;
    $('body').append('<div id="qqq_lightbox_bg"></div>');
    this.bg = $('#qqq_lightbox_bg');
    this.content = $(content);
    this.content.hide();
    this.visible = false;
    this.content.addClass('lightbox_content');
    this.content.css('z-index', 1002);
    this.content.find('a[data-role="ajax"]').click(function (e) {
        e.preventDefault();
        var href = $(this).prop('href');
        $.ajax({
            type: 'POST',
            url: href,
            success: function (data) {
                lb.hide();
                airport.refresh_ui(data);
            }
        });
    });
};

airport.LightBox.prototype.show = function() {
    if (!this.visible) {
        this.bg.fadeIn();
        this.content.css('display', 'inline-block');
        this.content.center();
        this.content.fadeIn();
        this.visible = true;
    }
};

airport.LightBox.prototype.hide = function() {
    if (this.visible) {
        this.bg.fadeOut();
        this.content.fadeOut();
        this.visible = false;
    }
};
