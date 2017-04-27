"""
    just mucking around with the OGS REST API. Not much error checking except to figure out what does what.
    see also: https://github.com/sousys/ogs/blob/master/ogs.py and https://forums.online-go.com/t/oauth2-best-practice/1701

    hmm have been coding in C++ too much lately... this all needs a more pythonic touch

    NOTE to self: reads/writes out the retrieved game list to games_lists.tmp so we can easily skip to the next interesting phase :D 
"""

import requests
import os
import sys
import json
import credentials as kredz

G_DEV_GAME_LIST_FNAME='games_lists.tmp'
G_SGF_SAVE_DIR='saved_games_sgf'

def get_oauth_tok():
    """ login. need the oauth token for all subsequent requests """
    r = requests.post('https://online-go.com/oauth2/token/', 
        data={'username': kredz.user, 
        'password': kredz.passwd, 
        'client_id': kredz.client_id, 
        'client_secret': kredz.client_secret, 
        'grant_type': 'password'})

    if (r.status_code != 200):
        print('error logging in: {}'.format(r.status_code))
        return None
    else:
        oath_tok = r.json()['access_token']
        print('login status: {}, access_token: {}'.format(r.status_code, oath_tok))
        return oath_tok

def get_userid(oauth_headers, username):
    """ get the user ID for a given username. ID's, not usernames, are required in most requests (i think?)"""
    r = requests.get('http://online-go.com/api/v1/players/?username={}'.format(username), 
        headers=oauth_headers)

    if (r.status_code != 200):
        print('error getting user id for {}: {}'.format(username, r.status_code))
        return None
    else:
        user_id = r.json()['results'][0]['id'] # <-- are OGS usernames unique?
        print('username: {} has id {}'.format(username, user_id))
        return user_id

def get_game_list(oauth_headers, user_id):
    """ get a big ol json dump of game details for _all_ games a user has played"""
    r = requests.get('http://online-go.com/api/v1/players/{}/games/'.format(user_id), 
            headers=oauth_headers)

    if (r.status_code != 200):
        print('error getting users game list')
        return

    user_games_md = r.json()
    game_list = r.json()['results']
    next_page = user_games_md['next']

    print('user has {} games. retrieved details for: {} games. next: {}'.format(user_games_md['count'], len(game_list), next_page))

    # t'is page'inated
    while next_page:
        print('getting next page of games: {}'.format(next_page))
        r = requests.get(next_page, headers=oauth_headers)
        if r.status_code != 200:
            print('\terror getting next chunk of games list')
            break

        game_list += r.json()['results']
        print('len of games is now {}'.format(len(game_list)))
        next_page = r.json()['next']
        print('\tgot {} more games.'.format(len(r.json()['results'])))

    return game_list

def get_sgf(oauth_headers, game_id):
    """ get raw SGF string of single game """
    r = requests.get('http://online-go.com/api/v1/games/{}/sgf/'.format(game_id), 
            headers=oauth_headers)

    if r.status_code != 200:
        print('\terror getting game for id: {}. Error: {}'.format(game_id, r.status_code))
        return ''
    else:
        return r.text

def simple_sgf_dump(oauth_headers, games_list):
    """ simply download all games and save them to a dir, with timestamp as filename"""
    if not os.path.exists(G_SGF_SAVE_DIR):
        os.makedirs(G_SGF_SAVE_DIR)

    print('saving games in SGF format to: {}'.format(G_SGF_SAVE_DIR))
    i=0;n=len(games_list)
    for g in games_list:
        i+=1
        sys.stdout.write('\r')
        sys.stdout.write('done: {}/{}'.format(i, n))
        sys.stdout.flush()
        open('{}/{}.sgf'.format(G_SGF_SAVE_DIR, g['started']), 'w').write(get_sgf(oauth_headers, g['id']))
    print('done')

def main():
    # try use cached games list to save poking the server during development
    cached_game_list = None
    if os.path.isfile(G_DEV_GAME_LIST_FNAME):
        print('cached game list exists at: {}'.format(G_DEV_GAME_LIST_FNAME), end=': ')
        try:
            cached_game_list = json.loads(open(G_DEV_GAME_LIST_FNAME, 'r').read())
            print('success')
        except:
            print('fail')

    oauth_headers = {'Authorization': 'Bearer {}'.format(get_oauth_tok())}

    # get user details
    r = requests.get('http://online-go.com/api/v1/me/', 
        headers=oauth_headers)
    if (r.status_code != 200):
        print('error getting user details: {}'.format(r.status_code))
        return

    user_id = r.json()['id']
    print('my user id: {}'.format(user_id))

    if cached_game_list:
        games_list = cached_game_list # makes dev quicker
    else:
        games_list = get_game_list(oauth_headers, user_id)
        open(G_DEV_GAME_LIST_FNAME, 'w').write(json.dumps(games_list))

    victories = []
    losses = []

    # messy little helpers
    win = lambda g: (g['black_lost'] and g['players']['white']['id'] == user_id) or (g['white_lost'] and g['players']['black']['id'] == user_id)
    oponent_username = lambda g: g['players']['white']['username'] if g['white'] != user_id else g['players']['black']['username']

    for game in games_list:
        if win(game):
            victories.append(game)
        else:
            losses.append(game)


    print('won: ')
    for g in victories:
        print('\t[{}] {}'.format(g['started'], oponent_username(g)))
    print('losses: ')
    for g in losses:
        print('\t[{}] {}'.format(g['started'], oponent_username(g)))


    # at this point we could categorise and save games any way we like... 
    # i'll just retrieve them and dump them out to a directory, with the start time as a (hopefully) unique filename
    simple_sgf_dump(oauth_headers, games_list)


if __name__ == '__main__':
    main()




'''
# -----------------------------------------------------------
# example from http://online-go.com/api/v1/players/{}/games/:
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "related": {
        "detail": "/api/v1/games/4"
      },
      "players": {
        "white": {
          "related": {
            "detail": "/api/v1/players/1"
          },
          "id": 1,
          "username": "anoek",
          "country": "us",
          "icon": "",
          "ranking": 10,
          "professional": false
        },
        "black": {
          "related": {
            "detail": "/api/v1/players/4"
          },
          "id": 4,
          "username": "matburt",
          "country": "us",
          "icon": "",
          "ranking": 11,
          "professional": false
        }
      },
      "id": 4,
      "name": "",
      "creator": 4,
      "mode": "game",
      "source": "play",
      "black": 4,
      "white": 1,
      "width": 19,
      "height": 19,
      "rules": "aga",
      "ranked": true,
      "handicap": 0,
      "komi": "0.50",
      "time_control": "simple",
      "time_per_move": 86400,
      "time_control_parameters": null,
      "disable_analysis": false,
      "tournament": null,
      "tournament_round": 0,
      "ladder": null,
      "pause_on_weekends": false,
      "outcome": "Timeout",
      "black_lost": false,
      "white_lost": true,
      "annulled": false,
      "started": "2012-11-15T17:25:57.920Z",
      "ended": "2012-11-25T06:22:59.261Z"
    }
  ]
}
'''