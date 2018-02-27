#!/usr/bin/env python3

## Importaciones
import logging
import subprocess
import sys
import threading
import re

import aiy.assistant.auth_helpers
import aiy.assistant.device_helpers
import aiy.audio
import aiy.voicehat

from google.assistant.library import Assistant
from google.assistant.library.event import EventType

# Para hacer peticiones a Webhooks
import requests

## Configuración loggin
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)

# Clase para ejecutar Assistant en segundo plano y así poder capturar las pulsaciones del botón
class MyAssistant(object):
    def __init__(self):
        self._task = threading.Thread(target=self._run_task)
        self._can_start_conversation = False
        self._assistant = None

    def start(self):
        # Inicia el loop de eventos de Assistant y comienza a procesarlos
        self._task.start()

    def _run_task(self):
        credentials = aiy.assistant.auth_helpers.get_assistant_credentials()
        device_id, model_id = aiy.assistant.device_helpers.get_ids(credentials)
        with Assistant(credentials, model_id) as assistant:
            self._assistant = assistant
            for event in assistant.start():
                self._process_event(event)

    def _process_event(self, event):
        status_ui = aiy.voicehat.get_status_ui()
        if event.type == EventType.ON_START_FINISHED:
            status_ui.status('ready')
            self._can_start_conversation = True
            # Inicia la detección de botón de voicehat
            aiy.voicehat.get_button().on_press(self._on_button_pressed)
            if sys.stdout.isatty():
                print('Say "OK, Google" or press the button, then speak. '
                      'Press Ctrl+C to quit...')

        elif event.type == EventType.ON_CONVERSATION_TURN_STARTED:
            self._can_start_conversation = False
            status_ui.status('listening')

        elif event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED and event.args:
            print('You said:', event.args['text'])
            text = event.args['text'].lower()
            handle_event(self, text)

        elif event.type == EventType.ON_END_OF_UTTERANCE:
            status_ui.status('thinking')

        elif event.type == EventType.ON_CONVERSATION_TURN_FINISHED:
            status_ui.status('ready')
            self._can_start_conversation = True

        elif event.type == EventType.ON_ASSISTANT_ERROR and event.args and event.args['is_fatal']:
            sys.exit(1)

    def _on_button_pressed(self):
        # Comprobamos si se puede iniciar una conversación 'self._can_start_conversation'
        # si es FALSO:
        # 1. La librería de assistant no está lista todavía; OR
        # 2. La librería de assistant ya está en una conversación
        if self._can_start_conversation:
            self._assistant.start_conversation()

## Definición de funciones

# Procesado del texto para request a IFTTT
def process_ifttt(text):
    api_key = 'bB165GMzAnKaqPXN64byEt'

    # Buscamos el disparador en el texto
    for word in text.split():
        if word in trigger:
            event_name = word

    # Generamos la URL de la request
    url = ('https://maker.ifttt.com/trigger/%s/with/key/%s' % (event_name, api_key))

    # Obtenemos los parámetros para la request
    payload = []

    # Enviamos la request
    r = requests.post(url, data=payload)

    # Procesamos la respuesta
    if 'text/html' in r.headers['Content-Type']:
        answer = r.text
    elif 'application/json' in r.headers['Content-Type']:
        json = r.json()
        answer = json[0]['message']
    else:
        answer = 'I couldn\'t send the request'

    aiy.audio.say(answer)

# Gestión de eventos
def handle_event(my, text):
    if text == 'power off':
        my._assistant.stop_conversation()
        power_off_pi()
    elif text == 'reboot':
        my._assistant.stop_conversation()
        reboot_pi()
    elif text == 'ip address':
        my._assistant.stop_conversation()
        say_ip()
    # Si alguna palabra coincide con el nombre de una bombilla
    elif any(word in trigger for word in text.split()):
        my._assistant.stop_conversation()
        # Procesamos el texto para ver enviar la request adecuada a IFTTT
        process_ifttt(text)

# Acciones locales
def power_off_pi():
    aiy.audio.say('Good bye!')
    subprocess.call('sudo shutdown now', shell=True)

def reboot_pi():
    aiy.audio.say('See you in a bit!')
    subprocess.call('sudo reboot', shell=True)

def say_ip():
    ip_address = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True)
    aiy.audio.say('My IP address is %s' % ip_address.decode('utf-8'))

## Función principal
def main():
    #Inicializamos el asistente
    MyAssistant().start()

if __name__ == '__main__':
    # Definimos disparadores de acciones
    trigger = ["hello","done"];

    # Lanzamos el asistente
    main()
