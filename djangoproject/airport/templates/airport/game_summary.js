var map,
    lightbox;

// draw polylines on the map
function draw_polylines(map) {
    var lat1, lon1, lat2, lon2;

    {% for ticket in tickets %}
    lat1 = {{ ticket.flight.origin.city.latitude }};
    lon1 = {{ ticket.flight.origin.city.longitude }};
    lat2 = {{ ticket.flight.destination.city.latitude }};
    lon2 = {{ ticket.flight.destination.city.longitude }};

    {% if forloop.first %}
        new google.maps.Marker({
            position: new google.maps.LatLng(lat1, lon1),
            map: map,
            icon: "{{ green_dot }}",
            title: "{{ ticket.flight.origin.city }}" });
    {% endif %}
    new google.maps.Polyline( {
        geodesic: true,
        map: map,
        path: [
            new google.maps.LatLng(lat1, lon1),
            new google.maps.LatLng(lat2, lon2),
        ],
        strokeColor: "{% cycle '#01004B' '#C70000' %}",
        strokeWeight: 3,
        strokeOpacity: 0.6
    });
    {% if ticket.goal %}
        new google.maps.Marker({
            position: new google.maps.LatLng(lat2, lon2),
            map: map,
            title: "{{ ticket.flight.destination.city }}",
            icon: "{{ gold_star }}" });
    {% endif %}
    {% endfor %}
}

function close_map(event) {
    event.preventDefault();
    lightbox.hide();
}

function show_map(event) {
    event.preventDefault();
    lightbox.show();
    google.maps.event.trigger(map, 'resize');
    map.setCenter(new google.maps.LatLng(39.833, -98.583));
}

function main() {
    map_options = {
            center: new google.maps.LatLng(39.833, -98.583),
            zoom: 4,
            disableDefaultUI: true,
            zoomControl: true,
            mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    map = new google.maps.Map(document.getElementById("map"), map_options);
    draw_polylines(map);
            
    $('#flight_schedule').memdraggable({handle: '#username'});
    $('#medal').memdraggable();
    $('#message_widget').memdraggable();

    $('#map_widget').draggable({handle: '#map_handle'});
    lightbox = new airport.LightBox('#map_widget');

    $('#close_map').click(close_map);
    $('#show_map').click(show_map);

    airport.messages('#message_box');

}

$(document).ready(main);
