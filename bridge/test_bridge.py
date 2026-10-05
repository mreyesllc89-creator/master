"""Offline HTTP and MT5 request regression tests: python -m unittest discover -s bridge."""
import copy
import http.client
import json
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch

import tv_mt5_bridge as bridge


def config():
    cfg = bridge.load_config(Path(__file__).with_name('config.example.json'))
    cfg['symbols']['XAUUSD']['mt5_symbol'] = 'GOLD'
    return cfg


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        with patch.dict(sys.modules, {'MetaTrader5': None}):
            self.broker = bridge.Broker(self.cfg)
        self.actions = []
        dry_sync = self.broker._dry_sync

        def record(*args):
            actions = dry_sync(*args)
            self.actions.append(actions)
            return actions

        self.broker._dry_sync = record
        self.server = bridge.ThreadingHTTPServer(('127.0.0.1', 0),
                                                bridge.make_handler(self.cfg, self.broker))
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def request(self, msg=None, path='/hook', method='POST', raw=None):
        body = raw if raw is not None else json.dumps(msg or {'symbol': 'XAUUSD', 'position': 'long'})
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body, {'Content-Type': 'application/json'})
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def alert(self, position, **kw):
        return self.request(dict(symbol='XAUUSD', position=position, **kw))

    def test_long_duplicate(self):
        self.assertEqual(self.alert('long'), 200)
        self.assertEqual(self.alert('long'), 200)
        self.assertEqual(self.actions, [['opened long 0.01 (dry run)'],
                                        ['already in sync (dry run)']])
        self.assertEqual(self.broker.dry_pos, {'GOLD': 'long'})

    def test_reverse(self):
        self.assertEqual(self.alert('long'), 200)
        self.assertEqual(self.alert('short'), 200)
        self.assertEqual(self.broker.dry_pos, {'GOLD': 'short'})
        self.assertEqual(self.actions[-1], ['closed long (dry run)',
                                           'opened short 0.01 (dry run)'])

    def test_flat(self):
        self.assertEqual(self.alert('short'), 200)
        self.assertEqual(self.alert('flat'), 200)
        self.assertEqual(self.broker.dry_pos, {'GOLD': 'flat'})
        self.assertEqual(self.actions[-1], ['closed short (dry run)'])

    def test_exchange_prefix(self):
        self.assertEqual(self.request({'symbol': 'OANDA:XAUUSD', 'position': 'long'}), 200)
        self.assertEqual(self.broker.dry_pos, {'GOLD': 'long'})

    def test_invalid_alerts(self):
        for msg in ({'symbol': 'UNKNOWN', 'position': 'long'},
                    {'symbol': 'XAUUSD', 'position': 'buy'},
                    {'symbol': 'XAUUSD', 'position': 'long', 'lots': .11},
                    {'symbol': 'XAUUSD', 'position': 'long', 'time': '2000-01-01T00:00:00Z'}):
            with self.subTest(msg=msg):
                self.assertEqual(self.request(msg), 400)
        self.assertEqual(self.broker.dry_pos, {})

    def test_invalid_json(self):
        for raw in ('{bad', '[]', 'null', '1', '"text"'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request(raw=raw), 400)

    def test_empty_secret(self):
        self.assertEqual(self.alert('long'), 200)

    def test_secret(self):
        self.cfg['secret'] = 'testing'
        self.assertEqual(self.alert('long'), 403)
        self.assertEqual(self.alert('long', secret='wrong'), 403)
        self.assertEqual(self.alert('long', secret='\u2603'), 403)
        self.assertEqual(self.alert('long', secret='testing'), 200)

    def test_routes(self):
        self.assertEqual(self.request(path='/wrong'), 404)
        self.assertEqual(self.request(method='GET'), 404)

    def test_broker_failure(self):
        with patch.object(self.broker, 'sync', side_effect=RuntimeError('offline')):
            self.assertEqual(self.alert('long'), 500)

    def test_bad_length(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request('POST', '/hook', '{}', {'Content-Length': 'bad'})
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 413)
        finally:
            conn.close()

    def test_bad_numeric_fields(self):
        for lots in (0, None, [], {}, 'no', float('nan'), float('inf')):
            with self.subTest(lots=lots):
                self.assertEqual(self.alert('long', lots=lots), 400)
        self.assertEqual(self.alert('long', time=123), 400)

    def test_comment_metadata(self):
        for label in ('XPW-15S_gold.1', ' A ', 'A' * 20):
            with self.subTest(label=label), patch.object(self.broker, 'sync', wraps=self.broker.sync) as sync:
                with self.assertLogs('bridge', level='INFO') as logs:
                    self.assertEqual(self.alert('long', comment=label), 200)
                sync.assert_called_once_with('GOLD', 'long', .01, 0, label)
                self.assertTrue(any(label in line for line in logs.output))

    def test_comment_default_and_empty(self):
        for fields in ({}, {'comment': ''}):
            with self.subTest(fields=fields), patch.object(self.broker, 'sync', wraps=self.broker.sync) as sync:
                self.assertEqual(self.alert('long', **fields), 200)
                sync.assert_called_once_with('GOLD', 'long', .01, 0, '')
        parsed = bridge.parse_alert(json.dumps({'symbol': 'XAUUSD', 'position': 'long'}), self.cfg)
        self.assertEqual(parsed, ('GOLD', 'long', .01, 0, ''))

    def test_invalid_comment(self):
        for label in (None, True, 1, [], {}, 'A' * 21, ' ', '   ', '\n',
                      'A\nB', 'A\rB', 'A\tB', 'A\x00B', '\u2603', 'caf\u00e9',
                      'A/B', 'A:B', 'A"B'):
            with self.subTest(label=label):
                self.assertEqual(self.alert('long', comment=label), 400)
        self.assertEqual(self.broker.dry_pos, {})


class FakeMT5(ModuleType):
    POSITION_TYPE_BUY = ORDER_TYPE_BUY = 0
    POSITION_TYPE_SELL = ORDER_TYPE_SELL = 1
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    SYMBOL_TRADE_EXECUTION_REQUEST, SYMBOL_TRADE_EXECUTION_INSTANT = 0, 1
    SYMBOL_TRADE_EXECUTION_MARKET, SYMBOL_TRADE_EXECUTION_EXCHANGE = 2, 3
    TRADE_ACTION_DEAL, ORDER_TIME_GTC = 1, 0
    TRADE_RETCODE_DONE, TRADE_RETCODE_DONE_PARTIAL = 10009, 10010

    def __init__(self):
        super().__init__('MetaTrader5')
        self.requests = []
        self.positions = []
        self.info = NS(filling_mode=3, trade_exemode=2, digits=2)
        self.tick = NS(ask=2000.12, bid=2000.02)
        self.terminal = NS(connected=True)
        self.account = NS(login=123, server='fake')
        self.initializations = []
        self.shutdowns = 0
        self.initialize_ok = self.select_ok = True
        self.result = NS(retcode=self.TRADE_RETCODE_DONE, order=42, comment='done')

    def initialize(self, **kw):
        self.initializations.append(kw)
        if self.initialize_ok:
            self.terminal = NS(connected=True)
        return self.initialize_ok

    def shutdown(self):
        self.shutdowns += 1

    def last_error(self):
        return (-1, 'fake error')

    def terminal_info(self):
        return self.terminal

    def account_info(self):
        return self.account

    def symbol_select(self, symbol, selected):
        return self.select_ok

    def positions_get(self, **kw):
        if self.positions is None:
            return None
        return tuple(p for p in self.positions if p.symbol == kw['symbol'])

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_send(self, req):
        self.requests.append(copy.deepcopy(req))
        if self.result is not None and self.result.retcode == self.TRADE_RETCODE_DONE:
            if 'position' in req:
                self.positions = [p for p in self.positions if p.ticket != req['position']]
            else:
                self.positions.append(NS(ticket=42, symbol=req['symbol'], magic=req['magic'],
                                         type=req['type'], volume=req['volume']))
        return self.result


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.cfg['dry_run'] = False
        self.fake = FakeMT5()
        self.inject = patch.dict(sys.modules, {'MetaTrader5': self.fake})
        self.inject.start()
        self.addCleanup(self.inject.stop)
        self.broker = bridge.Broker(self.cfg)

    def position(self, side=0, ticket=123, magic=None, volume=.03):
        return NS(symbol='GOLD', type=side, ticket=ticket, volume=volume,
                  magic=self.cfg['magic'] if magic is None else magic)

    def test_open_both_sides(self):
        for side, price, sl in ((0, 2000.12, 1999.00), (1, 2000.02, 2001.14)):
            with self.subTest(side=side):
                self.assertEqual(self.broker._open('GOLD', side, .02, 1.123), 42)
                req = self.fake.requests[-1]
                self.assertEqual(req['type'], side)
                self.assertEqual(req['volume'], .02)
                self.assertEqual(req['price'], price)
                self.assertEqual(req['sl'], sl)
                self.assertNotIn('position', req)
                self.assertEqual(req['magic'], self.cfg['magic'])
                self.assertEqual(req['action'], self.fake.TRADE_ACTION_DEAL)
                self.assertEqual(req['deviation'], self.cfg['deviation_points'])
                self.assertEqual(req['type_time'], self.fake.ORDER_TIME_GTC)
                self.assertEqual(req['type_filling'], self.fake.ORDER_FILLING_FOK)
                self.assertEqual(req['comment'], 'tv-bridge')

    def test_no_stop(self):
        self.broker._open('GOLD', 0, .01, 0)
        self.assertNotIn('sl', self.fake.requests[-1])

    def test_close_ticket_both_sides(self):
        for side, order_type, price in ((0, 1, 2000.02), (1, 0, 2000.12)):
            with self.subTest(side=side):
                self.broker._close(self.position(side))
                req = self.fake.requests[-1]
                self.assertEqual(req['position'], 123)
                self.assertEqual(req['type'], order_type)
                self.assertEqual(req['volume'], .03)
                self.assertEqual(req['price'], price)
                self.assertNotIn('sl', req)
                self.assertEqual(req['comment'], 'tv-bridge close')

    def test_labeled_open_and_close_both_sides(self):
        label = 'X' * 20
        for side, close_type in ((0, 1), (1, 0)):
            with self.subTest(side=side):
                self.broker._open('GOLD', side, .02, 1.123, label)
                opened = self.fake.requests[-1]
                self.assertEqual(opened['comment'], 'tv:' + label)
                self.assertEqual(opened['type'], side)
                self.assertEqual(opened['volume'], .02)
                self.assertIn('sl', opened)
                self.broker._close(self.position(side, ticket=123, volume=.02), label)
                closed = self.fake.requests[-1]
                self.assertEqual(closed['comment'], 'tv:' + label + ' close')
                self.assertEqual(closed['type'], close_type)
                self.assertEqual(closed['position'], 123)
                self.assertEqual(closed['volume'], .02)
                for req in (opened, closed):
                    self.assertLessEqual(len(req['comment']), 31)
                    self.assertTrue(req['comment'].isascii())
                    self.assertEqual(req['magic'], self.cfg['magic'])

    def test_labeled_reverse_and_changed_label_duplicate(self):
        self.broker.sync('GOLD', 'long', .02, 1, 'strategy-A')
        self.assertEqual(self.broker.sync('GOLD', 'long', .02, 1, 'strategy-B'),
                         ['already in sync'])
        self.assertEqual(len(self.fake.requests), 1)
        self.broker.sync('GOLD', 'short', .02, 1, 'strategy-C')
        self.assertEqual([r['comment'] for r in self.fake.requests],
                         ['tv:strategy-A', 'tv:strategy-C close', 'tv:strategy-C'])
        self.assertEqual([r['type'] for r in self.fake.requests], [0, 1, 1])
        self.assertEqual(self.fake.requests[1]['position'], 42)
        self.assertEqual([r['volume'] for r in self.fake.requests], [.02, .02, .02])
        self.assertTrue(all(r['magic'] == self.cfg['magic'] for r in self.fake.requests))

    def test_labels_share_position_ownership(self):
        foreign = self.position(ticket=999, magic=999)
        self.fake.positions = [foreign]
        self.broker.sync('GOLD', 'long', .01, 0, 'strategy-A')
        self.broker.sync('GOLD', 'flat', .01, 0, 'strategy-B')
        self.assertEqual(len(self.fake.requests), 2)
        self.assertEqual(self.fake.requests[-1]['position'], 42)
        self.assertEqual(self.fake.requests[-1]['comment'], 'tv:strategy-B close')
        self.assertEqual(self.fake.positions, [foreign])

    def test_concurrent_http_comments_do_not_bleed(self):
        self.cfg['symbols']['BTCUSDT'] = dict(mt5_symbol='BTCUSD', lots=.01,
                                              max_lots=.01, sl_distance=0)
        server = bridge.ThreadingHTTPServer(('127.0.0.1', 0),
                                           bridge.make_handler(self.cfg, self.broker))
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': .01}, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())

        self.addCleanup(stop)
        barrier = threading.Barrier(2)
        broker_sync = self.broker.sync

        def together(*args):
            barrier.wait(timeout=3)
            return broker_sync(*args)

        def request(symbol, position, label):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                body = json.dumps(dict(symbol=symbol, position=position, comment=label))
                conn.request('POST', '/hook', body, {'Content-Type': 'application/json'})
                response = conn.getresponse()
                response.read()
                return response.status
            finally:
                conn.close()

        with patch.object(self.broker, 'sync', side_effect=together), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(request, 'OANDA:XAUUSD', 'long', 'gold-A'),
                       pool.submit(request, 'BTCUSDT', 'short', 'bitcoin-B')]
            self.assertEqual([future.result(timeout=6) for future in futures], [200, 200])
        self.assertEqual(len(self.fake.requests), 2)
        requests = {req['symbol']: req for req in self.fake.requests}
        self.assertEqual(set(requests), {'GOLD', 'BTCUSD'})
        self.assertEqual(requests['GOLD']['comment'], 'tv:gold-A')
        self.assertEqual(requests['BTCUSD']['comment'], 'tv:bitcoin-B')
        self.assertEqual(requests['GOLD']['type'], 0)
        self.assertEqual(requests['BTCUSD']['type'], 1)
        self.assertTrue(all(req['magic'] == self.cfg['magic'] for req in requests.values()))

    def test_sync_duplicate_reverse_flat_and_magic(self):
        foreign = self.position(ticket=999, magic=999)
        self.fake.positions = [foreign]
        self.broker.sync('GOLD', 'long', .02, 1)
        self.assertEqual(self.broker.sync('GOLD', 'long', .02, 1), ['already in sync'])
        self.assertEqual(len(self.fake.requests), 1)
        self.broker.sync('GOLD', 'short', .02, 1)
        self.assertEqual([r['type'] for r in self.fake.requests], [0, 1, 1])
        self.assertEqual(self.fake.requests[1]['position'], 42)
        self.broker.sync('GOLD', 'flat', .02, 1)
        self.assertEqual(self.fake.requests[-1]['position'], 42)
        self.assertEqual(self.fake.requests[-1]['type'], 0)
        self.assertEqual(self.fake.positions, [foreign])

    def test_multiple_wrong_positions(self):
        self.fake.positions = [self.position(1, 11), self.position(1, 12)]
        self.broker.sync('GOLD', 'long', .01, 0)
        self.assertEqual([r.get('position') for r in self.fake.requests], [11, 12, None])

    def test_filling_modes(self):
        for execution, flags, expected in ((2, 1, 0), (2, 2, 1), (2, 3, 0),
                                           (3, 0, 2), (3, 4, 2), (0, 0, 0), (1, 0, 0)):
            with self.subTest(execution=execution, flags=flags):
                self.fake.info.trade_exemode = execution
                self.fake.info.filling_mode = flags
                self.assertEqual(self.broker._filling('GOLD'), expected)
        self.fake.info.trade_exemode = 2
        for flags in (0, 4):
            self.fake.info.filling_mode = flags
            with self.assertRaisesRegex(RuntimeError, 'requires FOK or IOC'):
                self.broker._open('GOLD', 0, .01, 0)
        self.assertEqual(self.fake.requests, [])

    def test_reconnect(self):
        for terminal in (None, NS(connected=False)):
            with self.subTest(terminal=terminal):
                self.fake.terminal = terminal
                self.broker.sync('GOLD', 'flat', .01, 0)
        self.assertEqual(len(self.fake.initializations), 3)
        self.assertEqual(self.fake.shutdowns, 2)

    def test_failed_reconnect(self):
        self.fake.terminal = None
        self.fake.initialize_ok = False
        with self.assertRaisesRegex(RuntimeError, 'initialize failed'):
            self.broker.sync('GOLD', 'long', .01, 0)
        self.assertEqual(self.fake.requests, [])

    def test_reconnect_keeps_config(self):
        self.cfg['mt5'] = dict(path='fake-terminal', login=123, password='fake', server='fake')
        self.fake.terminal = None
        self.broker.sync('GOLD', 'flat', .01, 0)
        self.assertEqual(self.fake.initializations[-1], self.cfg['mt5'])

    def test_reconnect_still_disconnected(self):
        def initialize(**kw):
            self.fake.terminal = NS(connected=False)
            return True
        self.fake.initialize = initialize
        self.fake.terminal = None
        with self.assertRaisesRegex(RuntimeError, 'disconnected'):
            self.broker.sync('GOLD', 'long', .01, 0)
        self.assertEqual(self.fake.requests, [])

    def test_missing_account(self):
        self.fake.account = None
        with self.assertRaisesRegex(RuntimeError, 'account unavailable'):
            bridge.Broker(self.cfg)

    def test_query_failure_cannot_open(self):
        self.fake.positions = None
        with self.assertRaisesRegex(RuntimeError, 'positions_get failed'):
            self.broker.sync('GOLD', 'long', .01, 0)
        self.assertEqual(self.fake.requests, [])

    def test_missing_symbol_or_quote(self):
        self.fake.info = None
        with self.assertRaisesRegex(RuntimeError, 'symbol_info failed'):
            self.broker._open('GOLD', 0, .01, 0)
        self.fake.tick = None
        with self.assertRaisesRegex(RuntimeError, 'no valid quote'):
            self.broker._close(self.position())
        self.fake.tick = NS(ask=0, bid=0)
        with self.assertRaisesRegex(RuntimeError, 'no valid quote'):
            self.broker._open('GOLD', 0, .01, 0)
        self.assertEqual(self.fake.requests, [])

    def test_order_failures_stop_reverse_without_retry(self):
        for result in (None, NS(retcode=10030, comment='bad filling'),
                       NS(retcode=10010, comment='partial')):
            with self.subTest(result=result):
                self.fake.requests.clear()
                self.fake.positions = [self.position()]
                self.fake.result = result
                with self.assertRaisesRegex(RuntimeError, 'order rejected'):
                    self.broker.sync('GOLD', 'short', .01, 0)
                self.assertEqual(len(self.fake.requests), 1)
                self.assertEqual(self.fake.requests[0]['position'], 123)

    def test_symbol_select_failure(self):
        self.fake.select_ok = False
        with self.assertRaisesRegex(RuntimeError, 'not available'):
            self.broker.sync('GOLD', 'long', .01, 0)
        self.assertEqual(self.fake.requests, [])


if __name__ == '__main__':
    unittest.main()
