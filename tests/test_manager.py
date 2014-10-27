# -*- coding: utf-8 -*-
from unittest import TestCase
import os
import panoramisk
from panoramisk import testing

try:  # pragma: no cover
    import asyncio
except ImportError:  # pragma: no cover
    import trollius as asyncio  # NOQA

try:
    from unittest import mock
except ImportError:
    import mock


class TestManager(TestCase):

    defaults = dict(
        async=False, testing=True,
        # loop=mock.MagicMock(),
        loop=asyncio.get_event_loop()
    )

    test_dir = os.path.join(os.path.dirname(__file__), 'data')

    def callFTU(self, stream=None, **config):
        if stream:
            config['stream'] = os.path.join(self.test_dir, stream)
        manager = testing.Manager(**dict(
            self.defaults,
            **config))
        if manager.loop:
            protocol = testing.Connection()
            protocol.factory = manager
            protocol.connection_made(mock.MagicMock())
            protocol.responses = mock.MagicMock()
            future = asyncio.Future()
            future.set_result((mock.MagicMock(), protocol))
            manager.protocol = protocol
            manager.connection_made(future)
        return manager

    def test_connection(self):
        manager = self.callFTU(loop=None)
        self.assertTrue(manager.connect())
        self.assertTrue('bla')

    def test_action(self):
        manager = self.callFTU(stream='pong')
        future = manager.send_action({'Action': 'Ping'})
        self.assertIn('ping', future.result())

        self.assertIn('ping', manager.send_action({'Action': 'Ping'}).lheaders)

        self.response.content = 'Response: Follows\r\nPing: Pong'
        self.assertIn('Ping', manager.send_action({'Action': 'Ping'}).content)

        self.response.content = 'Response: Success\r\nPing: Pong\r\nPing: Pong'
        self.assertIn('Ping', manager.send_action({'Action': 'Ping'}))
        self.assertEqual(manager.send_action({'Action': 'Ping'})['Ping'],
                         ['Pong', 'Pong'])

        self.response.content = 'Response: Follows\r\ncommand'
        resp = manager.send_command({'Action': 'Ping'})
        self.response.content = 'Response: Follows\r\ncommand\r\n'
        resp = manager.send_command({'Action': 'Ping'})
        self.assertTrue(resp.success)
        self.assertIn('command', resp.content)
        f = manager.send_action({'Action': 'Ping'}, callback=lambda _: None)
        manager.loop.run_until_complete(f)
        print('loop complete')

    def test_action_class(self):
        action = panoramisk.Action({'Action': 'Ping'})
        self.assertNotEqual(action.id, panoramisk.Action().id)
        self.assertIn('ActionID', str(action))
        self.assertIn('ActionID', str(panoramisk.Action()))

    def test_action_failed(self):
        manager = self.callFTU(use_http=True, url='http://host')
        self.response.content = 'Response: Failed\r\ncommand'
        action = panoramisk.Action({'Action': 'Ping'})
        resp = manager.send_command({'Action': 'Ping'})
        self.assertFalse(resp.success)
        self.assertIn('command', resp.iter_lines())

    def test_action_error(self):
        manager = self.callFTU(use_http=True)
        self.assertFalse(manager.send_action({'Action': 'Ping'}).success)

    def test_close(self):
        manager = self.callFTU(use_http=True, url='http://host')
        manager.close()

    def test_events(self):
        future = asyncio.Future()

        def callback(event, manager):
            future.set_result(event)

        manager = self.callFTU(use_http=True, url='http://host')
        manager.register_event('Peer*', callback)
        event = panoramisk.Message.from_line('Event: PeerStatus',
                                             manager.callbacks)
        self.assertTrue(event.success)
        self.assertEqual(event['Event'], 'PeerStatus')
        self.assertIn('Event', event)
        manager.dispatch(event, event.matches)
        self.assertTrue(event is future.result())

        event = panoramisk.Message.from_line('Event: NoPeerStatus',
                                             manager.callbacks)
        self.assertTrue(event is None)


class TestProtocol(TestCase):

    def callback(*args):
        pass

    def callFTU(self):
        conn = testing.Connection()
        conn.responses = mock.MagicMock()
        manager = testing.Manager()
        manager.register_event('Peer*', self.callback)
        manager.loop = asyncio.get_event_loop()
        conn.connection_made(mock.MagicMock())
        conn.factory = manager
        return conn

    def test_received(self):
        conn = self.callFTU()
        conn.data_received(b'Event: None\r\n\r\n')
        conn.data_received(b'Event: PeerStatus\r\nPeer: gawel\r\n\r\n')
        conn.data_received(b'Response: Follows\r\nPeer: gawel\r\n\r\n')
        conn.data_received(b'Response: Success\r\nPing: Pong\r\n\r\n')

    def test_send(self):
        conn = self.callFTU()
        self.assertTrue(isinstance(conn.send({}), asyncio.Future))
