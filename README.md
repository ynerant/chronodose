# Alertes IRC Vaccins

Ce bot donne des alertes de disponibilités de vaccin contre le covid-19,
accessible à tout adulte depuis le mardi 11 mai 2021, pourvu que le
rendez-vous soit pris la veille ou le jour-même afin de laisser la
priorité aux personnes les plus fragiles.

Le bot récupère les données collectées par
<https://vitemadose.covidtracker.fr/>, et en cas de disponibilités,
une alerte est levée sur un salon IRC.

## Configuration

La configuration se fait via un fichier YAML nommé ``config.yml``.

Pour commencer, copiez le fichier ``config.yml.example`` dans
``config.yml``.

### Configuration de la connexion au serveur IRC

Le bloc ``irc`` permet de configurer la connexion au serveur IRC.

* ``host`` indique l'hôte du serveur auquel se connecter (ex : irc.crans.org)
* ``nickname`` le pseudo à utiliser
* ``channel`` indique le salon à utiliser pour poster les alertes.

### Configuration des paramètres de recherche

Le bloc ``search`` permet de configurer les options de recherche,
afin de ne pas être alerté des disponibilités de toute la France.

Il s'agit d'une liste de lieux à rechercher. Ils se présentent de la forme :

* ``position`` : coordonnées du point à rechercher
  * ``longitude`` : longitude du point
  * ``latitude``: latitude du point
  * ``city`` : nom du point (pour un meilleur affichage)
* ``radius`` : rayon maximal en kilomètres de recherche autour du point
  précédent
* ``departements`` : départements voisins à rechercher, toujours dans la
  limite du rayon défini
* ``mentions`` : en cas d'alerte, indique la ou les personnes à mentionner

Enfin, le paramètre ``delay`` permet de définir le délai d'attente en
secondes entre 2 recherches (par défaut 5 minutes).

## Lancer le bot

Python 3.9 est requis. Le code pourrait sans difficulté être adapté pour des
versions inférieures.

Vous aurez également besoin des bibliothèques ``requests`` et ``yaml``.

Il suffit ensuite de lancer le fichier ``chronodose.py``. De préférence,
à lancer sur un serveur dans un screen ou un tmux.
