#!/usr/bin/env python
from paho.mqtt import client as mqtt
from mqtt_wrapper import MqttWrapperFactory
import signal
import sys
from GameStarter import GameStarter
import time
from functools import wraps
from threading import Event, Thread
import os

class SpacehackConfiguration:
    GAME_START_DELAY = 5.0
    JOIN_GAME_DELAY = 1.0
    LEAVE_GAME_DELAY = 0.5

    def root_topic():
        env_topic = os.environ.get('SH_TOPIC_PREFIX_OVERRIDE') or 'spacehack'
        return ''.join(c if c not in '\/.#$+_' else '-' for c in env_topic) + '/'

class SpacehackFactory:
    def mqtt_factory():
        return MqttWrapperFactory(topic_prefix=SpacehackConfiguration.root_topic())

    def game_starter():
        sc = SpacehackConfiguration
        return GameStarter(sc.GAME_START_DELAY, sc.JOIN_GAME_DELAY, sc.LEAVE_GAME_DELAY)

class Service:
    running_services = []

    @classmethod
    def register(cls, service):
        cls.running_services.append(service)

    @classmethod
    def deregister(cls, service):
        cls.running_services.remove(service)

    @classmethod
    def stop_all(cls):
        for service in cls.running_services:
            service.stop()

    @classmethod
    def wait_all(cls):
        for service in cls.running_services:
            service.wait()

    def __init__(self):
        self.stopped = Event()
        self.init_done = Event()

    def stop(self):
        self.stopped.set()

    def await_init_done(self):
        self.init_done.wait()

    def wait(self, *args):
        self.svc_thread.join(*args)

    def sleep(self, time):
        self.stopped.wait(time)
        if self.stopped.isSet():
            raise Exception('Service stopped')

    def init(self):
        # Some services might not need to do setup, so it's OK not to override
        pass

    def run(self):
        raise Exception("Service.run(): Implement this in subclass")

    def cleanup(self):
        # Some services might not need to clean up, so it's OK not to override
        pass

    def service_thread(self):
        Service.register(self)
        self.init()
        self.init_done.set()
        try:
            self.run()
        finally:
            self.cleanup()
        Service.deregister(self)

    def start(self, synchronous_init=False):
        self.svc_thread = Thread(target=self.service_thread)
        self.svc_thread.start()
        if synchronous_init:
            self.await_init_done()

class Lobby(Service):
    def __init__(self, mqtt_factory):
        super(Lobby, self).__init__()
        self.mqtt = mqtt_factory.new()

    def handle_join(self, topic, payload):
        _, console, *_ = topic.split('/')
        player = self.gamestarter.player(console)
        print('Payload "%s" on "%s"' %(payload, topic))
        if payload == '1':
            player.push()
        elif payload == '0':
            player.release()
        else:
            print('Unknown payload "%s" on "%s"' %(payload, topic))

    def init(self):
        self.mqtt.connect()
        self.gamestarter = SpacehackFactory.game_starter()
        self.mqtt.sub('+/join', self.handle_join)

    def run(self):
        while(not self.stopped.isSet()):
            self.sleep(0.05)
            self.gamestarter.step_time(0.05)
            if(self.gamestarter.should_start):
                # TODO: Start a GameRunner service, wait for init
                self.mqtt.pub('start', ','.join(self.gamestarter.joined_players))
                self.gamestarter.reset()

    def cleanup(self):
        self.mqtt.stop()

class GameRunner(Service):
    def __init__(self, mqtt_factory, game_subtopic):
        super(GameRunner, self).__init__()
        self.mqtt = mqtt_factory.new(game_subtopic)

    def init(self):
        self.mqtt.connect()
        self.mqtt.sub('+/ready')

    def run(self):
        self.mqtt.pub('splash/text', '***** SPACEHACK *****')
        self.sleep(4.0)
        self.mqtt.pub('splash/text', 'Wheeeeeeeeeeeeee')
        self.sleep(10.0)

    def cleanup(self):
        self.mqtt.stop()

class SpacehackHost:
    def __init__(self, mqtt_factory=SpacehackFactory.mqtt_factory()):
        self.mqtt_factory=mqtt_factory
        self.lobby = Lobby(self.mqtt_factory)

    def stop(self):
        Service.stop_all()
        Service.wait_all()

    def start(self):
        self.lobby.start()

    def wait(self):
        Service.wait_all()


if __name__ == '__main__':
    sh = SpacehackHost()
    def signal_handler(sig, frame):
        print('Exit')
        sh.stop()
        sh.wait()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    sh.start()
    sh.wait()
