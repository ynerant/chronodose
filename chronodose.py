#!/usr/bin/env python3

from dataclasses import dataclass
from datetime import date
from math import acos, cos, pi, sin
import os
import requests
import sys
from threading import Thread
from time import sleep
import yaml

from irc import IRCClient


@dataclass
class Config:
    @dataclass
    class IRCConfig:
        nickname: str = ""
        host: str = ""
        channel: str = ""


    @dataclass
    class SearchConfig:
        position: "Location" = None
        radius: float = 0
        departements: list[int] = None
        mentions: list[str] = None


    irc: "IRCConfig" = None
    search: list["SearchConfig"] = None

    def __init__(self, irc: "IRCConfig", search: list["SearchConfig"]):
        if isinstance(irc, dict):
            irc = Config.IRCConfig(**irc)
        if not search:
            search = []
        search = [Config.SearchConfig(**sc) if isinstance(sc, dict) else sc for sc in search]
        for s in search:
            if isinstance(s.position, dict):
                s.position = Location(**s.position)

        self.irc = irc
        self.search = search


@dataclass
class Location:
    longitude: float = 0.0
    latitude: float = 0.0
    city: str = ""

    def distance(self, other: "Location") -> float:
        earth_radius = 6378

        phi_a, phi_b = self.latitude * pi / 180, other.latitude * pi / 180
        lambda_a, lambda_b = self.longitude * pi / 180, other.longitude * pi / 180
        unit_dist = acos(sin(phi_a) * sin(phi_b) \
                + cos(phi_a) * cos(phi_b) * cos(lambda_b - lambda_a))

        return earth_radius * unit_dist


@dataclass
class CentreMetadata:
    address: str = ""
    phone_number: str = ""
    business_hours: dict = None


@dataclass
class Centre:
    departement: str = ""
    nom: str = ""
    url: str = ""
    location: Location = None
    metadata: CentreMetadata = None
    prochain_rdv: str = ""
    plateforme: str = "Doctolib"
    type: str = "vaccination-center"
    appointment_count: int = 0
    internal_id: str = ""
    vaccine_type: list[str] = None
    appointment_by_phone_only: bool = False
    erreur: any = None
    last_scan_with_availabilities: str = ""
    appointment_schedules: list[dict] = None
    gid: str = ""


def check_dpt(dpt_number: int, position: Location, radius: int = 20):
    """
    Recherche de rendez-vous disponibles pour les majeurs non-prioritaires
    dans le département indiqué.
    Renvoie une liste de couples (centre, nombre de doses dispo).
    """
    res = requests.get(f'https://vitemadose.gitlab.io/vitemadose/{dpt_number}.json').json()

    last_update = res['last_updated']
    centres_dispo = res['centres_disponibles']
    centres_indispo = res['centres_indisponibles']
    print(len(centres_dispo), "centres disponibles sur", len(centres_indispo), "dans le", dpt_number)

    places = []

    for centre in centres_dispo:
        centre = Centre(**centre)
        centre.location = Location(**centre.location)
        centre.metadata = CentreMetadata(**centre.metadata)

        if centre.location.distance(position) > radius:
            # Centre trop loin
            continue

        for schedule in centre.appointment_schedules:
            if schedule['name'] == 'chronodose':
                if schedule['total']:
                    # Places dispo en chronodose
                    places.append((centre, schedule['total']))
    return places


def main():
    if not os.path.isfile('config.yml'):
        print("Le fichier de configuration n'existe pas. "
              "Commencez par copier l'exemple depuis config.yml.example.", file=sys.stderr)
        exit(1)

    # Chargement de la configuration
    with open('config.yml') as f:
        config = yaml.safe_load(f)
    config = Config(**config)

    irc_client = IRCClient(config.irc.host, config.irc.nickname)
    Thread(target=irc_client.start).start()
    # Connexion à IRC
    sleep(10)
    irc_client.join(config.irc.channel)
    irc_client.privmsg(config.irc.channel, 'coucou')

    already_indicated = []

    def msg(*mesg: str) -> None:
        # Afficher un message dans la console et sur IRC
        print(*mesg)
        irc_client.privmsg(config.irc.channel, ' '.join(str(a) for a in mesg))

    while True:
        for search in config.search:
            places = []
            for dpt in search.departements:
                places.extend(check_dpt(dpt, search.position, search.radius))

            if not places:
                print("Pas de place disponible autour de", search.position.city)
                continue

            print(sum(place[1] for place in places), "doses disponibles autour de", search.position.city)
            for centre, count in places:
                if (centre.internal_id, date.today()) in already_indicated:
                    # Message déjà envoyé, on spam pas
                    continue
                already_indicated.append((centre.internal_id, date.today()))

                msg(count, "doses dans le centre de", centre.nom)
                msg("Type de vaccin :", ", ".join(centre.vaccine_type))
                msg(centre.metadata.address, centre.metadata.phone_number)
                msg("Réserver sur", centre.url)
                msg(*search.mentions)
                msg(" ")

        # 5 minutes
        sleep(300)


if __name__ == '__main__':
    main()
