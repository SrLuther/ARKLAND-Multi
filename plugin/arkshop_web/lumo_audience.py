"""Fresh, read-only audience check; no identities or credentials are returned."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


def query_game_server(server, *, settings, hosts, sanitize, execute, parse):
    """Only a fresh, recognized ListPlayers reply proves presence or emptiness."""
    try:
        config = settings(str(server.get('server_id') or ''))
        port = int(server.get('rcon_port') or config.get('rcon_port') or 27020)
        password = sanitize(str(server.get('rcon_password') or config.get('rcon_password') or ''))
        if not password or not 1 <= port <= 65535:
            return {'status': 'unavailable', 'players': []}
        for host in hosts(server, config):
            try:
                reply = execute(host, port, password, 'ListPlayers', timeout=6.0, connect_retries=1)
                players = parse(reply)
                if players:
                    return {'status': 'online', 'players': [True] * len(players)}
                if re.fullmatch(r'\s*No Players Connected\.?\s*', str(reply or '').strip('\x00'), re.I):
                    return {'status': 'online', 'players': []}
            except Exception:
                continue
    except Exception:
        pass
    return {'status': 'unavailable', 'players': []}


def game_audience_snapshot(servers, query):
    targets = list(servers)
    if not targets:
        return {'ok': True, 'has_players': False, 'confirmed_players': 0}
    pool = ThreadPoolExecutor(max_workers=min(8, len(targets)), thread_name_prefix='lumo-audience')
    futures = [pool.submit(query, server) for server in targets]
    unknown = False
    try:
        for future in as_completed(futures):
            try:
                result = future.result()
                if result.get('status') != 'online':
                    unknown = True
                    continue
                players = result.get('players')
                if not isinstance(players, list):
                    unknown = True
                    continue
                if players:
                    # Lower bound, not an advertised cluster total. One fresh
                    # positive suffices; don't wait for unrelated map timeouts.
                    return {'ok': True, 'has_players': True, 'confirmed_players': len(players)}
            except Exception:
                unknown = True
        return {'ok': not unknown, 'has_players': False, 'confirmed_players': 0}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
