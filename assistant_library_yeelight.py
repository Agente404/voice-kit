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

from yeelight import discover_bulbs, Bulb

## Configuración loggin
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)

## Definición de clases
# Clase para definir nuestras bombillas
class YeelightBulb(object):
    def __init__(self, name, ip, support, model, power):
        self.name = name
        self.ip = ip
        self.support = support
        self.model = model
        self.power = power
        self.bulb = Bulb(self.ip, auto_on=True)

    def set_power(self, mode):
        answer = ('%s is now %s' % (self.name, mode))

        if mode == "on" and self.power != "on":
            self.bulb.turn_on()
            self.power = mode
        elif mode == "off" and self.power != "off":
            self.bulb.turn_off()
            self.power = mode
        elif mode == "toggle":
            self.bulb.toggle()

            if self.power == "on":
                self.power = "off"
            else:
                self.power = "on"
        else:
            answer = ('%s is already %s' % (self.name, self.power))

        return answer

    def set_brightness(self, value):
        self.bulb.set_brightness(value)
        answer = ('%s brightness value set' % self.name)
        return answer

    def set_rgb(self, color, color_name):
        if "set_rgb" in self.support:
            self.bulb.set_rgb(color[0],color[1],color[2])
            answer = ('%s color set to %s' % (self.name, color_name))
        else:
            answer = ('%s doesn\'t support RGB color mode' % self.name)

        return answer

    def set_color_temp(self, temp):
        if "set_ct_abx" in self.support:
            if 1700 <= temp <= 6500:
                self.bulb.set_color_temp(temp)
                answer = ('%s color temperature set' % self.name)
            else:
                answer = 'Color temperature must be between 1700 and 6500 degrees'
        else:
            answer = ('%s doesn\'t support color temperature adjustment' % self.name)

        return answer

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

# #Definición de funciones
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
    elif any(word in my_bulbs for word in text.split()):
        my._assistant.stop_conversation()
        # Procesamos el texto para ver qué hacer con dicha bombilla
        process_yeelight(text)

# Inicialización de las bombillas yeelight
def init_yeelight():
    # Inicializamos la lista de bombillas
    bulb_list = {}

    # Buscamos las bombillas
    print('Looking for bulbs')
    discovered_bulbs = discover_bulbs()
    discovered_len = len(discovered_bulbs)

    if discovered_len <= 0:
        # Si no se encuentran bombillas informamos al usuario
        print('No bulbs found')
    else:
        #Si se encuentran bombillas, decimos cuantas y las parseamos
        print('%s bulb%s found.' % (discovered_len,('s' if  discovered_len > 1 else '')))

        for bulb in discovered_bulbs:
            ip = bulb["ip"]
            support = bulb["capabilities"]["support"]
            model = bulb["capabilities"]["model"]
            power = bulb["capabilities"]["power"]

            #Comprobamos que la bombilla tiene nombre
            if bulb['capabilities']['name']:
                name = bulb['capabilities']['name'].lower()
            else:
                print('------------------------------')
                print('Bulb IP is: %s' % ip)
                print('This Yeelight %s has no name' % model)

                #Si no lo tine asignamos un nombre a la bombilla
                target_bulb = Bulb(ip)
                name = input('Enter name of the bulb: ').lower()
                target_bulb.set_name(name)

            #Añadimos la bombilla al diciconario
            bulb_list[name] = YeelightBulb(name,ip,support,model,power)

    return bulb_list

# Procesado de las acciones a realizar con la bombilla
def process_yeelight(text):
    # Definimos los nombres de los colores
    colors = {
        'red':[255,0,0],
        'orange':[255,159,0],
        'yellow':[255,255,0],
        'lime':[159,255,0],
        'green': [0,255,0],
        'cyan green':[0,255,159],
        'cyan':[0,255,255],
        'azure':[0,159,255],
        'blue':[0,0,255],
        'purple':[159,0,255],
        'magenta':[255,0,255],
        'fuchsia':[255,0,159],
        'white':[255,255,255]
    }

    # Definimos la respuesta del asistente
    answer = "I don't know what to do"

    # Definimos la bombilla objetivo
    for word in text.split():
        if word in my_bulbs:
            target_bulb = my_bulbs[word]

    # Condición para encender o apagar la bombilla
    if ("turn" or "toggle") in text:
        if "on" in text:
            answer = target_bulb.set_power("on")
        elif "off" in text:
            answer = target_bulb.set_power("off")
        elif "toggle" in text:
            answer = target_bulb.set_power("toggle")

    # Condición para gestionar el brillo
    if ("brightness" or "bright") in text:
        if "full" in text:
            value = 100
        else:
            value = int(re.search('\d+[^%]', text).group(0))

        answer = target_bulb.set_brightness(value)

    # Condición para gestionar el color de la bombilla
    if ("color" or "rgb") and not ("temp" or "temperature") in text:
        for word in text.split():
            for key, value in colors.items():
                if word in key.lower():
                    answer = target_bulb.set_rgb(colors[key], key)

    # Condición para gestionar la temperatura de color
    if ("temp" or "temperature") in text:
        value = int(re.search('\d+', text).group(0))
        answer = target_bulb.set_color_temp(value)

    # Una vez evaluadas las condiciones, damos una respuesta
    aiy.audio.say(answer)

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
    # Buscamos bombillas y las inicializamos
    my_bulbs = init_yeelight()

    # Lanzamos el asistente
    main()
