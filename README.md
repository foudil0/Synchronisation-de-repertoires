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

 Fonctionnalité | Description 
----------------|-------------|
 Surveillance des fichiers locaux | Détecter toute modification (création, suppression, modification) dans un répertoire. | 
Création automatique de commits | Enregistrer les changements détectés sous forme de commits locaux. |
Push vers le serveur Git | Envoyer les commits locaux sur le serveur central. |
 Pull depuis le serveur Git | Récupérer les mises à jour effectuées sur le serveur. |
 Gestion des conflits | Détecter les conflits et créer une duplication des fichiers concernés. |

---

## Fonctionnalités complémentaires

Fonctionnalités qui viennent enrichir le noyau minimal sans être indispensables au fonctionnement de base.

 Fonctionnalité | Description |
----------------|-------------|
Interface de configuration | Choisir le répertoire à surveiller et la fréquence de synchronisation. |
 Journal d’activité | Enregistrer les actions (commits, push, pull, conflits). | 
 Notifications utilisateur | Prévenir l’utilisateur en cas de conflit ou d’erreur. |

---

