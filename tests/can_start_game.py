# RUN: ./tbin/test_coverage.sh %s %t

from libs.test_utils import TimeoutTest
from host import Lobby, HostFactory
import config

conf = config.build()

mqtt_factory = HostFactory.mqtt_factory(conf)
l = Lobby(conf, mqtt_factory)

c = mqtt_factory.new()
c.connect()

test = TimeoutTest(10.0)

def start(topic, payload):
    """ Handler for start topic messages """
    # Check that two players are joined
    assert len(payload.split(',')) == 3
    # Test has passed
    test.passed()

def act():
    # Register handler
    c.sub('start', start)
    l.await_init_done()
    # Simulate players joining
    l.wait(0.1)
    c.pub('1/join', '1')
    c.pub('2/join', '1')
    test.await_completion()

test.run(l.start, act)
