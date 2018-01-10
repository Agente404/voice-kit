#!/usr/bin/env python3

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

## Configuramos el log de eventos
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)

## Clase para ejecutar Assistant en segundo plano y así poder capturar las pulsaciones del botón
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
            handle_event(text, self)

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

## Gestión de eventos
def handle_event(text, my):
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
    elif any(word in text for word in [bulb['capabilities']['name'].lower() for bulb in my_bulbs]):
        my._assistant.stop_conversation()
        # Procesamos el texto para ver qué hacer con dicha bombilla
        process_yeelight(text)
    
    
## Inicializa las bombillas yeelight
def init_yeelight():
    # Al ejecutarse descubre las bombillas
    bulb_list = discover_bulbs() 
    bulb_len = len(bulb_list)

    print('Looking for bulbs')
                    
    if bulb_len <= 0:
        print('No bulbs found')
    else:        
        print('%s bulb%s found.' % (bulb_len,('s' if  bulb_len > 1 else '')))
        
        refresh = 0
        
        for bulb in bulb_list:
            # Comprobamos que todas tienen nombre, si no lo tienen...
            if not bulb['capabilities']['name']:
                target_bulb = Bulb(bulb['ip'])                
                print('------------------------------')
                print('Bulb IP is: %s' % bulb['ip'])
                print('This Yeelight %s has no name' % bulb['capabilities']['model'])
                
                #Asignamos un nombre a la bombilla
                bulb_name = input('Enter name of the bulb: ')            
                target_bulb.set_name(bulb_name)
                refresh = 1
        
        #Actualizamos la lista de bombillas
        if refresh:
            print('Updating bulbs lists')
            bulb_list = discover_bulbs()

    return bulb_list

## Procesado de las acciones a realizar con la bombilla
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
    
    # Buscamos la bombilla objetivo   
    for word in text.split():
        for bulb in my_bulbs:
            capabilities = bulb.get('capabilities')            
            if word == capabilities['name'].lower():
                target_bulb = Bulb(bulb['ip'], auto_on=True)
                target_name = capabilities['name']
                target_support = capabilities['support']

    # Condición para encender o apagar la bombilla
    if ("turn" or "toggle") in text:
        if "on" in text:
            target_bulb.turn_on()
            answer = 'Bulb is now on'
        elif "off" in text:
            target_bulb.turn_off()
            answer = 'Bulb is now on'
        elif "toggle" in text:
            target_bulb.toggle()
            answer = 'Light is toggled'

    # Condición para gestionar el brillo
    if ("brightness" or "bright") in text.split():
        if "full" in text:
            value = 100
        else:
            value = int(re.search('\d+[^%]', text).group(0))
            
        target_bulb.set_brightness(value)
        answer = 'Brightness value set'

    # Condición para gestionar el color de la bombilla
    if ("color" or "rgb") and not ("temp" or "temperature") in text:       
        if "set_rgb" in target_support:
            for word in text.split():
                for key, value in colors.items():
                    if word in key.lower():
                        target_bulb.set_rgb(colors[key][0],colors[key][1],colors[key][2])
                        answer = 'Color set'
        else:
            answer = 'This bulb isn\'t RGB capable'

    # Condición para gestionar la temperatura de color
    if ("temp" or "temperature") in text:
        if "set_ct_abx" in target_support:
            value = int(re.search('\d+', text).group(0))
            if 1700 <= value <= 6500:
                target_bulb.set_color_temp(value)
                answer = 'Color temperature set'
            else:
                answer = 'Color temperature must be between 1700 and 6500 degrees'
        else:
            answer = 'This bulb doesn\'t support color temperature adjustment'
    
    # Una vez evaluadas las condiciones, damos una respuesta
    aiy.audio.say(answer)

## Acciones locales
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
