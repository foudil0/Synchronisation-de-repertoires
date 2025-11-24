# Synchronisation de répertoires

## Objectif du projet

Développer un outil permettant la **synchronisation automatique de répertoires entre plusieurs machines** en utilisant un **serveur Git** pour centraliser les fichiers.

L’application côté client doit :
- surveiller les fichiers locaux ;
- créer automatiquement des commits en cas de modification ;
- synchroniser les changements avec le serveur (push/pull) ;
- gérer les conflits éventuels.

---

## Noyau minimal 

Fonctionnalités indispensables pour obtenir une version fonctionnelle de base.

 Fonctionnalité | Description |Pyhton standard | Bib tièrce | outils independants|
----------------|-------------|----------------|------------|--------------------|
 Surveillance des fichiers locaux | Détecter toute modification (création, suppression, modification) dans un répertoire. | Os, pathlib, time | watchdog | inotifywait
Création automatique de commits | Enregistrer les changements détectés sous forme de commits locaux. | subprocess et commandes git | GitPyhton | pygit2
Push vers le serveur Git | Envoyer les commits locaux sur le serveur central. | subprocess et commandes git | GitPyhton | pygit2
 Pull depuis le serveur Git | Récupérer les mises à jour effectuées sur le serveur. |subprocess et commandes git | GitPyhton | pygit2
 Gestion des conflits | Détecter les conflits et créer une duplication des fichiers concernés. | | GitPyhton | 

---

## Fonctionnalités complémentaires

Fonctionnalités qui viennent enrichir le noyau minimal sans être indispensables au fonctionnement de base.

 Fonctionnalité | Description |Pyhton standard | Bib tièrce | outils independants|
----------------|-------------|----------------|------------|--------------------|
Interface de configuration | Choisir le répertoire à surveiller et la fréquence de synchronisation. |json|PyMAL,tkinter, PyQt6
 Journal d’activité | Enregistrer les actions (commits, push, pull, conflits). | logging | loguru
 Notifications utilisateur | Prévenir l’utilisateur en cas de conflit ou d’erreur. |

---

## Librairies: 

#### Os, pathlib, time: 
- **Service rendu:** parcourir les repertoires, lire les fichiers, et verifier les dates de modification
- **Limites:** pas de surveillence en temps reel, et n'est pas efficase sur de gros repertoires
- **Installation:** deja incluse 
- **Utilisation:** simple
- **Comptabilité:** parfaite avec tous les OS
- **Maintenance et doc:** excellente car c'est une bib pyhton standart

#### Watchdog
- **Service rendu:** Surveillence en temps reel des evenements
- **Limites:** depends d'autres librairies natives (comme inotify sur Linux)
- **Installation:** pip install watchdog
- **Utilisation:** simple
- **Comptabilité:** très bonne avec tous les OS
- **Maintenance et doc:** Bien documentée

#### Inotifywait
- **Service rendu:** Surveillence en temps reel ultra rapide
- **Limites:** Linux seulement
- **Maintenance et doc:** Bien documentée

--

#### Subprocess + commandes git:
- **Service rendu:** excecuter commandes git 
- **limites:** pas d'API git, gestion manuelle d'erreur, très très fragile
- **Installation:** incluse
- **Utilisation:** Simple 
- **Comptabilité:** depend de Git installé sur la machine

#### GitPython:
- **Services rendu:** Fonctions pour excecuter les commandes git **(repo.is_dirty(), repo.git.add(), repo.index.commit())** ainsi que la gestion des branches et conflits
- **Limites:** Lente sur les gros depots
- **installation:** pip install GitPython
- **Utilisation:** simple, permet l'automatisation
- **comptabilité:** tres bonne
- **Maintenance et doc:** active depuis +10 ans 

#### pygit2:
- **Services rendu:** API Git avancées 
- **limites:** Installation complexe
- **Utilisation:** plus technique 
- **Maintenance et doc:** pas très bonne au grand publique
