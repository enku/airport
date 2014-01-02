"""
Airport
"""
from . import models
from .lib import websocket

VERSION = '1.1.0'


def start_game(game):
    """Start a Game and a GameThread to run it."""
    game.begin()
    send_message('start_game_thread', game.pk)


def take_turn(game, now=None, throw_wrench=True):
    if game.state in (game.GAME_OVER, game.NOT_STARTED, game.PAUSED):
        return now

    winners_before = game.winners()
    now = now or game.time
    arrivals = {}

    if not hasattr(game, '_airports'):
        game._airports = game.airports.distinct()

    if throw_wrench:
        send_message('throw_wrench', game.pk)

    for airport in game._airports:
        players_arrived = handle_flights(game, airport, now)
        for player in players_arrived:
            arrivals[player.pk] = airport

    handle_players(game, now, winners_before, arrivals)
    return now


def handle_flights(game, airport, now=None):
    announce = models.Message.announce
    now = now or game.time
    players_arrived = []

    # Departing flights
    flights = airport.next_flights(now, auto_create=False)
    for flight in flights:
        in_flight = flight.in_flight(now)
        ticket_holders = flight.passengers.distinct()

        for player in ticket_holders:
            if not (in_flight and player.airport):
                continue

            # player has taken off
            player.airport = None
            player.save()
            game.record_ticket_purchase(player, flight)
            msg = '{0} has departed {1}.'
            msg = msg.format(player.user.username, airport)
            announce(player, msg, game, message_type='PLAYERACTION')

    # Arriving flights
    flights = models.Flight.objects.arrived_but_not_flagged(game, now)
    flights = flights.filter(destination=airport)  # for this airport

    for flight in flights:
        ticket_holders = flight.passengers.distinct()
        destination = flight.destination

        for player in ticket_holders:
            # player has landed
            msg = '{0} has arrived at {1}.'
            msg = msg.format(player.user.username, destination)
            announce(player, msg, game, message_type='PLAYERACTION')
            players_arrived.append(player)

            ach = player.next_goal(game)
            if ach and ach.goal.city == player.ticket.destination.city:
                ach.fulfill(player.ticket.arrival_time)

            player.airport = destination
            player.ticket = None
            player.save()

        flight.state = 'Arrived'
        flight.save()

    airport.next_flights(now, auto_create=True)
    return players_arrived


def handle_players(game, now, winners_before, arrivals):
    """Update each player in game."""
    broadcast = models.Message.broadcast
    players = game.players.distinct()

    # FIXME: If the data previously sent hasn't changed, we shouldn't
    # re-send the data.  Actually, the data will almost always be the same
    # since we sent the time... so first we should probably work on not
    # sending the game time in each update... but since the game time is
    # different than "real" time, we can't rely on the client to know the
    # game time on its own.  Hmmm...
    for player in players:
        player_info = player.info(game, now)
        if player.pk in arrivals:
            notify = 'You have arrived at {0}.'.format(arrivals[player.pk])
            player_info['notify'] = notify
        send_message('info', player_info)

    winners = game.winners()
    if not winners_before and winners:
        if len(winners) == 1:
            msg = '{0} has won {1}.'
            msg = msg.format(winners[0].user.username, game)
            broadcast(msg, game, message_type='WINNER', finishers=True)
        else:
            msg = '{0}: {1}-way tie for 1st place.'
            msg = msg.format(game, len(winners))
            broadcast(msg, game, message_type='WINNER', finishers=True)
            for winner in winners:
                msg = '{0} is a winner!'
                msg = msg.format(winner.user.username)
                broadcast(msg, game, message_type='WINNER', finishers=True)

    # if all players have achieved all goals, end the game
    if game.is_over():
        game.end()
        send_message('game_ended', game.pk)


def send_message(message_type, data):
    return websocket.IPCHandler.send_message(message_type, data)
