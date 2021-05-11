#!/usr/bin/env python3

from dataclasses import dataclass
from datetime import date
from math import acos, cos, pi, sin
import requests
from threading import Thread
from time import sleep

from irc import IRCClient


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
    gif = Location(latitude=48.7090418, longitude=2.1648068, city="Gif-sur-Yvette")
    lyon = Location(latitude=45.7579502, longitude=4.8001017, city="Lyon")
    chambéry = Location(latitude=45.5822142, longitude=5.8713341, city="Chambéry")
    nantes = Location(latitude=47.2382007, longitude=-1.6300954, city="Nantes")
    marseille = Location(latitude=43.2803692, longitude=5.3104571, city="Marseille")

    irc_client = IRCClient('irc.crans.org', 'chronodose')
    Thread(target=irc_client.start).start()
    sleep(10)
    irc_client.join('#chronodose')
    irc_client.privmsg('#chronodose', 'coucou')

    already_indicated = []

    def msg(*mesg: str) -> None:
        # Afficher un message dans la console et sur IRC
        print(*mesg)
        irc_client.privmsg('#chronodose', ' '.join(str(a) for a in mesg))

    while True:
        places = {}
        for dpt, ville in [(91, gif), (92, gif), (94, gif), (78, gif), (69, lyon),
                (73, chambéry), (44, nantes), (13, marseille)]:
            places[dpt] = check_dpt(dpt, ville)

        for dpt, places in places.items():
            if not places:
                print("Pas de dose disponible dans le", dpt)
                continue
            print(sum(place[1] for place in places), "doses disponibles dans le", dpt)
            for centre, count in places:
                if (centre.internal_id, date.today()) in already_indicated:
                    # Message déjà envoyé, on spam pas
                    continue
                already_indicated.append((centre.internal_id, date.today()))

                msg(count, "doses dans le centre de", centre.nom)
                msg("Type de vaccin :", ", ".join(centre.vaccine_type))
                msg(centre.metadata.address, centre.metadata.phone_number)
                msg("Réserver sur", centre.url)
                msg(" ")

        # 5 minutes
        sleep(300)


if __name__ == '__main__':
    main()
