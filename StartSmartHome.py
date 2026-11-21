#!/usr/bin/python

from integration.levitonSH import LevitonIntegration
from integration.smartthingSH import SmartThingsIntegration
from integration.life360SH import Life360Integration
from integration.weatherSH import WeatherIntegration
from integration.tailwindSH import TailwindIQ3Integration
from integration.iftt_smsSH import Iftt

from libraries.util import LoggerSH, TimeTriggerSH, SunSH, EventsScheduler, SignalHandler
from libraries.util import is_between_time, calculate_time, merge_dict, format_time_hhmmss, minute_to_hhmm, get_time_now
import asyncio
from libraries.definitions import *
import os
import time
import datetime

# todo: send email when a device become offline and back online
# todo: List rules from webcore to complete


def main():
    signal_handler = SignalHandler()
    presence_domicile = True

    # ================ Required for async function smartthing  =====
    if os.name == 'nt':  # nt = windows, posix = linux
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # ================ Logger initialisation =====
    hb = LoggerSH(heart_beat_delay=60, log_file_name="heartbeat.txt", to_console=False)
    switch_state_logger = LoggerSH(log_file_name="smartlog.txt", to_console=True)

    # ================ Time Trigger  initialisation =====
    time_trigger = TimeTriggerSH()
    scheduler = EventsScheduler(switch_state_logger)

    # ================ SMARTTHINGS initialisation =====
    session_smartthing = SmartThingsIntegration(switch_state_logger)
    asyncio.run(session_smartthing.refresh_all_devices_status())
    session_smartthing.set_switch_state([VS_COUCHER, VS_DEJEUNER, VS_DISABLE_AUTO_LIGHT_OFF,
                                         VS_SOIRE_TELE, VS_SOUPER, VS_TRAVAIL, VS_LEANNE_OUT], OFF)
    all_smartthings_switch = session_smartthing.get_all_switch_state()
    all_smartthings_presence = session_smartthing.get_all_presence_state()
    all_smartthings_devices = merge_dict(all_smartthings_switch, all_smartthings_presence)

    # ================ LEVITON initialisation ========

    session_leviton = LevitonIntegration(LEVITON_USER_NAME, switch_state_logger)
    session_leviton.connect()
    all_leviton_switches = session_leviton.get_all_switches()

    # ================ LIFE360 initialisation ========
    life360 = Life360Integration(LIFE360_USER_NAME, 'Famille Trudelle', 'Domicile', module_enable=True)
    all_life360_devices = life360.get_all_presence_state()

    # ================ iQ3 TailWind initialisation ========
    iq3 = TailwindIQ3Integration(ip=IQ3_IP, module_enable=True)
    iq3.start()
    garage_devices = iq3.get_state()
    next_door_closing = time.monotonic()
    need_to_close_garage_door = False
    garage_door_warning = False

    # ================ Weather initialisation =====
    weather = WeatherIntegration(LATITUDE, LONGITUDE)

    # ================ Iftt initialisation =====
    iftt = Iftt()

    # ================ Sun calculator  initialisation =====
    sun = SunSH(LATITUDE, LONGITUDE)
    sunrise = sun.sunrise()
    sunset = sun.sunset()
    switch_state_logger.log_message(f"{sunrise=}, {sunset=}")

    # ==== Merge All Dictionary and log initial value ====
    all_devices = merge_dict(all_leviton_switches, all_smartthings_devices, all_life360_devices, garage_devices)
    for device in all_devices:
        switch_state_logger.log_changes(device, all_devices[device]['state'])

    next_loop = time.monotonic()
    while signal_handler.can_run():
        # Process all schedule task and run them if needed
        scheduler.run(blocking=False)

        # Update some key variables
        auto_off = all_devices['vsDisableAutoLightOff']['state'] == OFF

        # At midnight calculate the next sunrise and sunset
        if time_trigger.time_is("00:00"):
            sunrise = sun.sunrise()
            sunset = sun.sunset()
            switch_state_logger.log_message(f"{sunrise=}, {sunset=}")

        weather_conditions = weather.read_weather_condition()

        # Detect the presence mode: someone arrives
        if all_devices[PRESENCE_MATHIEU]['state'] == PRESENT \
                or all_devices[PRESENCE_STEPHANE]['state'] == PRESENT\
                or all_devices[PRESENCE_LEANNE]['state'] == PRESENT:
            if presence_domicile is False:
                presence_domicile = True
                rule_name = "Quelqu'un Arrive"
                switch_state_logger.log_message(f"{rule_name}: Domicile: Present")

        # Detect the presence mode: house is empty
        if all_devices[PRESENCE_MATHIEU]['state'] == ABSENT \
                and all_devices[PRESENCE_STEPHANE]['state'] == ABSENT\
                and all_devices[PRESENCE_LEANNE]['state'] == ABSENT:
            if presence_domicile is True:
                presence_domicile = False
                rule_name = "Tout le monde est parti"
                switch_state_logger.log_message(f"{rule_name}: Domicile: Absent")
                session_leviton.set_switch([LUM_COMPTOIRE,
                                            LUM_CUISINE,
                                            LUM_PASSAGE,
                                            LUM_SALLE_A_MANGER,
                                            LUM_FOYER,
                                            LUM_ESCALIER_SOUS_SOL,
                                            LUM_ESCALIER_GARAGE], OFF)
                need_to_close_garage_door = True

        # Some light at sunset in the house
        if time_trigger.time_is(calculate_time("00:30", "before", sunset)) \
                and presence_domicile is True:
            rule_name = "Un peu de lumière le soir"
            switch_state_logger.log_message(f"{rule_name=}")
            if all_devices['Lumière Salle à manger']['state'] != ON:
                session_leviton.set_level('Lumière Salle à manger', 70)
            if all_devices['Lumière foyer']['state'] != ON:
                session_leviton.set_level('Lumière foyer', 50)

        # Spot outside at sun set
        if time_trigger.time_is(calculate_time("00:30", "after", sunset)):
            rule_name = "Spot au coucher du soleil"
            switch_state_logger.log_message(f"{rule_name=}")
            session_leviton.set_switch(SPOT_EXTERIEUR_AVANT, ON)

        if time.monotonic() >= next_loop:
            next_loop = time.monotonic() + 0.5
            # ================ SMARTTHING update  =====================
            asyncio.run(session_smartthing.refresh_all_devices_status())
            all_smartthing_switch = session_smartthing.get_all_switch_state()
            all_smartthing_presence = session_smartthing.get_all_presence_state()
            all_smartthing_devices_updated = merge_dict(all_smartthing_switch, all_smartthing_presence)

            # ================ LEVITON update  ========================
            if not session_leviton.connected:
                if session_leviton.connection_failed:
                    # todo: logic to log that we are disconnected and log at every disconnection attempt
                    hb.log_changes("Disconnected at", str(session_leviton.disconnect_time))
                session_leviton.reconnect()
            else:
                hb.log_alive()
            all_leviton_switches_updated = session_leviton.get_all_switches()

            # ================ LIFE360 update  ========================
            all_life360_devices_updated = life360.get_all_presence_state()

            # ================ iq3 update  ========================
            all_iq3_devices_updated = iq3.get_state()

            # ================ PROCESSING Based on state change ===================
            all_devices_updated = merge_dict(
                all_smartthing_devices_updated,
                all_leviton_switches_updated,
                all_life360_devices_updated,
                all_iq3_devices_updated
            )

            # ======= Will reset VirtualSwitch if for whatever reason it has been On for more than 2 minutes ===========
            # goal is to prevent fix possible mis-sync with virtual switch when state change would be not detected
            for device_name in all_devices_updated.keys():
                if device_name in [VS_SOUPER, VS_COUCHER, VS_TRAVAIL, VS_SOIRE_TELE, VS_DEJEUNER] \
                        and all_devices_updated[device_name]['virtual'] is True\
                        and all_devices_updated[device_name]['state'] == ON \
                        and datetime.datetime.now() >= all_devices_updated[device_name]['last_update']\
                        + datetime.timedelta(minutes=2):
                    session_smartthing.set_switch_state(device_name, OFF)

            for device_name in all_devices_updated.keys():
                device_value_updated = all_devices_updated[device_name]['state']
                device_value_previous = all_devices[device_name]['state']
                if device_value_previous != device_value_updated:
                    all_devices[device_name]['state'] = device_value_updated
                    switch_state_logger.log_changes(device_name, device_value_updated)
                    ########################
                    # Automation rules
                    ########################

                    # Link light from kitchen
                    if device_name == 'Lumière Comptoire' \
                            and device_value_updated == ON\
                            and is_between_time(calculate_time("00:30", "after", sunrise), "19:30")\
                            and all_devices_updated['vsSouper']['state'] == OFF:
                        rule_name = "Lier comptoire - Cuisine: On"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Cuisine', ON)

                    if device_name == 'Lumière Cuisine' \
                            and device_value_updated == ON\
                            and is_between_time(calculate_time("00:30", "after", sunrise), "19:30")\
                            and all_devices_updated['vsSouper']['state'] == OFF:
                        rule_name = "Lier cuisine - comptoire:ON"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Comptoire', ON)

                    if device_name == 'Lumière Comptoire' and device_value_updated == OFF\
                            and all_devices_updated['vsSouper']['state'] == OFF:
                        rule_name = "Lier comptoire - Cuisine: OFF"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Cuisine', OFF)

                    if device_name == 'Lumière Cuisine' and device_value_updated == OFF\
                            and all_devices_updated['vsSouper']['state'] == OFF:
                        rule_name = "Lier cuisine - comptoire: OFF"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Comptoire', OFF)

                    # Link les lumières de l'escalier
                    if device_name == 'Lumière Escalier sous-sol':
                        rule_name = "Lier Escalier sous-sol - Escalier garage"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Escalier garage', device_value_updated)

                    if device_name == 'Lumière Escalier garage':
                        rule_name = "Lier Escalier garage - Escalier sous-sol"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Escalier sous-sol', device_value_updated)

                    # Salle d'eau
                    if device_name == FAN_SALLE_D_EAU:
                        if device_value_updated == ON and auto_off is True:
                            scheduler.enter(20 * 60, 1, session_leviton.set_switch, argument=(FAN_SALLE_D_EAU, OFF))
                        else:
                            scheduler.cancel(FAN_SALLE_D_EAU)

                    if device_name == LUM_SALLE_D_EAU:
                        if device_value_updated == ON and auto_off is True:
                            scheduler.enter(15 * 60, 1, session_leviton.set_switch, argument=(LUM_SALLE_D_EAU, OFF))
                        else:
                            scheduler.cancel(LUM_SALLE_D_EAU)

                    # Si mathieu se couche, on ferme toute les lumières du sous sol
                    if device_name == 'Lumière Mathieu' \
                            and device_value_updated == OFF\
                            and is_between_time("21:00", "05:00"):
                        rule_name = "Fermer sous sol, Mathieu se couche"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière divan', OFF)
                        session_leviton.set_switch('Lumière salle de jeu', OFF)
                        session_leviton.set_switch('Lumière Escalier garage', OFF)
                        session_leviton.set_switch('Lumière Escalier sous-sol', OFF)

                    # Si mathieu part, on ferme les lumières du sous-sol
                    if device_name == PRESENCE_MATHIEU and device_value_updated == ABSENT:
                        rule_name = "Mathieu part"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Mathieu', OFF)
                        session_leviton.set_switch('Lumière divan', OFF)
                        session_leviton.set_switch('Lumière salle de jeu', OFF)
                        session_leviton.set_switch('Lumière Escalier garage', OFF)
                        session_leviton.set_switch('Lumière Escalier sous-sol', OFF)

                    # Si Stephane part on ferme les lumières de sa chambre
                    if device_name == PRESENCE_STEPHANE and device_value_updated == ABSENT:
                        rule_name = "Stephane part"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière  Lit', OFF)

                    # Si Léanne part on ferme les lumières de sa chambre
                    if device_name == PRESENCE_LEANNE and device_value_updated == ABSENT:
                        rule_name = "Léanne part"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Chambre Léanne', OFF)

                    # Si quelqu'un arrive la nuit, on lui ouvre les lumière de l'entrée et ferme apres 15 minutes
                    if device_name in (PRESENCE_MATHIEU, PRESENCE_STEPHANE, PRESENCE_LEANNE) \
                            and device_value_updated == PRESENT\
                            and is_between_time(sunset, sunrise):
                        rule_name = "Quelqu'un arrive la nuit"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Spot en avant', ON)
                        session_leviton.set_switch('Lumière devant', ON)
                        session_leviton.set_switch('Lumière entrée', ON)
                        if auto_off is True:
                            scheduler.enter(5 * 60, 1, session_leviton.set_switch, argument=("Lumière devant", OFF))
                            scheduler.enter(10 * 60, 1, session_leviton.set_switch, argument=("Lumière entrée", OFF))
                        if is_between_time("22:00", sunrise) and auto_off is True:
                            # Si il est passé 22h: on va fermer les lumieres dans 15 minutes
                            scheduler.enter(5 * 60, 1, session_leviton.set_switch, argument=('Spot en avant', OFF))

                        # Si c'est mathieu qui arrive on lui ouvre le chemin vers sa chambre
                        if device_name == PRESENCE_MATHIEU:
                            rule_name = "Mathieu Arrive"
                            switch_state_logger.log_changes(rule_name, "Trig-sub")
                            if is_between_time(sunset, sunrise):
                                session_leviton.set_switch('Lumière divan', ON)
                                session_leviton.set_switch('Lumière salle de jeu', ON)
                                session_leviton.set_switch('Lumière Escalier garage', ON)
                                session_leviton.set_switch('Lumière Escalier sous-sol', ON)
                                session_leviton.set_switch('Lumière Mathieu', ON)

                        # Si c'est stephane qui arrive on lui ouvre le chemin vers sa chambre
                        if device_name == PRESENCE_STEPHANE:
                            rule_name = "Stephane Arrive la nuit"
                            switch_state_logger.log_changes(rule_name, "Trig-sub")
                            if is_between_time("22:00", sunrise):
                                session_leviton.set_level('Lumière  Lit', 15)
                            if all_devices['Lumière foyer']['state'] != ON:
                                session_leviton.set_level('Lumière foyer', 25)

                        # Si c'est Léanne qui arrive on lui ouvre le chemin vers sa chambre
                        if device_name == PRESENCE_LEANNE:
                            rule_name = "Léanne Arrive la nuit"
                            switch_state_logger.log_changes(rule_name, "Trig-sub")
                            if is_between_time("22:00", sunrise):
                                # session_leviton.set_level('Lumière Chambre Léanne', 15)
                                session_smartthing.set_switch_state(LUM_FENETRE_LEANNE, ON)
                            if all_devices['Lumière foyer']['state'] != ON:
                                session_leviton.set_level('Lumière foyer', 25)

                    # On allume ou eteint les lumieres de Noel
                    if device_name == "Lumière de Noel":
                        rule_name = "Lumière de Noel: toggle"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_smartthing.set_switch_state(['Globe 1', 'Globe 2', 'Globe 3'], device_value_updated)

                    # Pour le souper ajuster les lumières
                    if device_name == "vsSouper" and device_value_updated == ON:
                        rule_name = "On Soupe"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch('Lumière Comptoire', OFF)
                        if is_between_time(calculate_time("00:30", "before", sunset), "22:00"):
                            session_leviton.set_switch('Lumière Cuisine', ON)
                            session_leviton.set_level('Lumière Salle à manger', 70)
                        session_leviton.set_switch('Lumière Passage', OFF)
                        scheduler.enter(1 * 60, 1, session_smartthing.set_switch_state,
                                        argument=('vsSouper', OFF))

                    # Pour le dejeuner ajuster les lumières
                    if device_name == "vsDejeuner" and device_value_updated == ON:
                        rule_name = "On Déjeune"
                        switch_state_logger.log_message(f"{rule_name=}")
                        switch_state_logger.log_message(f"Weather:{weather_conditions['log_string']=}")
                        switch_state_logger.log_message(f"Weather Offset:{weather_conditions['time_offset']}")
                        session_smartthing.set_switch_state('vsDejeuner', OFF)
                        if is_between_time("04:00", calculate_time(weather_conditions['time_offset'], "after", sunrise)):
                            session_leviton.set_level('Lumière foyer', 50)
                            session_leviton.set_level('Lumière Salle à manger', 100)
                            session_leviton.set_switch('Lumière Comptoire', ON)
                            session_leviton.set_switch('Lumière Cuisine', ON)
                        session_smartthing.set_switch_state(['Lumière de Noel'], ON)
                        scheduler.enter(60, 1, session_leviton.set_switch, argument=("Lumière  Lit", OFF))

                    # Pour le coucher on ferme les lumières au premiers
                    if device_name == "vsCoucher" and device_value_updated == ON:
                        rule_name = "On se Couche"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_smartthing.set_switch_state("vsCoucher", OFF)
                        session_leviton.set_level('Lumière  Lit', 25)
                        session_leviton.set_switch('Spot en avant', OFF)
                        session_leviton.set_switch('Lumière devant', OFF)
                        session_leviton.set_switch('Lumière entrée', OFF)
                        session_leviton.set_switch('Lumière Passage', OFF)
                        session_leviton.set_switch('Lumière Comptoire', OFF)
                        session_leviton.set_switch('Lumière Cuisine', OFF)
                        session_leviton.set_switch('Lumière Salle à manger', OFF)
                        session_leviton.set_switch('Lampe', OFF)
                        scheduler.enter(90, 1, session_leviton.set_switch, argument=(LUM_FOYER, OFF))
                        session_smartthing.set_switch_state(['Lumière de Noel'], OFF)
                        if all_devices_updated[PRESENCE_MATHIEU]['state'] == ABSENT:
                            session_leviton.set_switch('Lumière Mathieu', OFF)
                            session_leviton.set_switch('Lumière divan', OFF)
                            session_leviton.set_switch('Lumière salle de jeu', OFF)
                            session_leviton.set_switch('Lumière Escalier garage', OFF)
                            session_leviton.set_switch('Lumière Escalier sous-sol', OFF)

                    # Je vais travailler ... de la maison on fermes des lumieres
                    if device_name == "vsTravail" and device_value_updated == ON:
                        rule_name = "Je Travail"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_smartthing.set_switch_state("vsTravail", OFF)
                        session_leviton.set_switch('Lumière  Lit', OFF)
                        session_leviton.set_switch('Lumière foyer', OFF)
                        session_leviton.set_switch('Lumière Comptoire', OFF)
                        session_leviton.set_switch('Lumière Cuisine', OFF)
                        session_leviton.set_switch('Lumière Salle à manger', OFF)

                    # Pour regarder la TV on ferme des lumières
                    if device_name == "vsSoirée télé" and device_value_updated == ON:
                        rule_name = "Soirée Télé"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_smartthing.set_switch_state("vsSoirée télé", OFF)
                        session_leviton.set_switch('Lumière entrée', OFF)
                        session_leviton.set_switch('Lumière Passage', OFF)
                        session_leviton.set_switch('Lumière Comptoire', OFF)
                        session_leviton.set_switch('Lumière Cuisine', OFF)
                        session_leviton.set_switch('Lumière  Palier', OFF)
                        session_leviton.set_switch('Lumière Salle à manger', OFF)
                        session_leviton.set_level('Lumière foyer', 40)
                        session_leviton.set_level('Lampe', 40)

                    # On veux rentrer dans la maison par le garage et la porte principale
                    if device_name == GARAGE_DOOR and device_value_updated == OPENED:
                        rule_name = "Ajuste Lumiere Porte Garage Ouvre"
                        switch_state_logger.log_message(f"{rule_name=}")

                        if all_devices_updated[LUM_EXTERIEUR_DEVANT]['state'] == ON:
                            session_leviton.set_switch(LUM_EXTERIEUR_DEVANT, OFF)
                        if is_between_time(sunset, sunrise):
                            session_leviton.set_switch([LUM_ESCALIER_GARAGE, LUM_ESCALIER_SOUS_SOL], ON)

                    # Gestion pseudo intelligent que Léanne n'est pas la le soir
                    if device_name == VS_LEANNE_OUT and device_value_updated == ON:
                        rule_name = "Léanne est sortie le soir, on lui prepare des lumieres"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch(LUM_EXTERIEUR_DEVANT, ON)
                        session_leviton.set_level(LUM_FOYER, 20)
                        session_leviton.set_level(LUM_CH_LEANNE, 15)
                    if all_devices_updated[VS_LEANNE_OUT]['state'] == ON and device_name == LUM_CH_LEANNE and device_value_updated == OFF:
                        rule_name = "Léanne est sortie, mais semble se coucher, on ferme les lumieres"
                        switch_state_logger.log_message(f"{rule_name=}")
                        session_leviton.set_switch(LUM_EXTERIEUR_DEVANT, OFF)
                        session_leviton.set_switch(LUM_FOYER, OFF)
                        session_smartthing.set_switch_state(VS_LEANNE_OUT, OFF)

            # ALl Garage door related rules
            garage_door_status = all_devices_updated[GARAGE_DOOR]['state']
            garage_door_update = all_devices_updated[GARAGE_DOOR]['last_update']
            garage_state_duration_minutes = (datetime.datetime.now() - garage_door_update).seconds/60

            if garage_door_status == OPENED and time.monotonic() >= next_door_closing and auto_off is True:
                if weather_conditions['temperature'] < 5 and garage_state_duration_minutes >= 10:
                    if garage_door_warning is False:
                        iftt.send_sms("Garage Door will close in 5 minutes")
                        garage_door_warning = True
                    if garage_state_duration_minutes >= 15:
                        garage_door_warning = False
                        rule_name = "Close  Garage < 5oC"
                        iftt.send_sms(rule_name)
                        switch_state_logger.log_message(f"{rule_name=}")
                        next_door_closing = time.monotonic() + 90
                        iq3.close(GARAGE_DOOR)
                if weather_conditions['temperature'] < 10 and garage_state_duration_minutes >= 25:
                    if garage_door_warning is False:
                        iftt.send_sms("Garage Door will close in 5 minutes")
                        garage_door_warning = True
                    if garage_state_duration_minutes >= 30:
                        garage_door_warning = False
                        rule_name = "Close  Garage < 10oC"
                        iftt.send_sms(rule_name)
                        switch_state_logger.log_message(f"{rule_name=}")
                        next_door_closing = time.monotonic() + 90
                        iq3.close(GARAGE_DOOR)
                if is_between_time(calculate_time("00:45", "after", sunset), sunrise)\
                        and garage_state_duration_minutes >= 10:
                    if garage_door_warning is False:
                        iftt.send_sms("Garage Door will close in 5 minutes")
                        garage_door_warning = True
                    if garage_state_duration_minutes >= 15:
                        garage_door_warning = False
                        rule_name = "Close  Garage After Sunset"
                        iftt.send_sms(rule_name)
                        switch_state_logger.log_message(f"{rule_name=}")
                        next_door_closing = time.monotonic() + 90
                        iq3.close(GARAGE_DOOR)
                if need_to_close_garage_door is True:
                    rule_name = "Close  Garage no one home"
                    iftt.send_sms(rule_name)
                    switch_state_logger.log_message(f"{rule_name=}")
                    next_door_closing = time.monotonic() + 90
                    iq3.close(GARAGE_DOOR)
            if garage_door_status == CLOSED:
                need_to_close_garage_door = False
        else:
            time.sleep(.1)
    iq3.run_thread = False
    print("Ending StartSmartHome")


if __name__ == '__main__':
    main()
