# Experimentos con Google AIY Voice kit

A continuación dejo una serie de scripts para realizar ciertas tareas con Assistant Library y Voice Kit. Uso Assistant Library puesto que en Europa no tenemos disponible Cloud Speech API para Voice Kit.

Prerequisitos:
* Tener AIY Voice Kit funcionando ([tutorial](https://agente404.com/2017/12/31/primeros-pasos-con-google-aiy-voice-kit/))

## assistant_library_yeelight.py
Script para controlar bombillas Yeelight haciendo uso de python-yeelight. A día de hoy las funciones soportadas son:
* Encendido y apagado
* Brillo
* Color
* Temperatura de color

Dependencias:
* [python-yeelight](https://gitlab.com/stavros/python-yeelight)

Testeado con Yeelight RGBW bulb y Yeelight Mono bulb. Puedes leer más acerca de este script en [El Blog del Agente 404](https://agente404.com/2018/01/10/controlando-luces-yeelight-con-voice-kit/)

## assistant_library_ifttt.py
Este script permite lanzar un evento Webhooks en IFTTT:

Dependencias:
* [requests](http://docs.python-requests.org/en/master/)

Este script es un "Work in progress" no ha sido testeado todavía.
