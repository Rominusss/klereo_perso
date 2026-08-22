# Klereo (perso) — fork patché pour Home Assistant

Fork personnel de [ha-klereo](https://github.com/JonBasse/ha-klereo) par JonBasse, avec des corrections et ajouts basés sur des diagnostics réels d'installation (voir `CHANGELOG` ci-dessous). Installé sous le domaine `klereo_perso`, il peut cohabiter sans conflit avec l'intégration officielle `klereo` installée via HACS.

## Pourquoi ce fork ?

- **Correctif** : sur le firmware actuel, les consignes réglables (température, pH, redox, chlore) sont exposées par l'API Klereo sous `details["params"]`, pas sous `details["RegulModes"]` comme le suppose l'intégration d'origine. Résultat : la consigne d'eau (`ConsigneEau`) n'était jamais créée en entité `number`. Ce fork lit les deux emplacements.
- **Nouvelles entités** : consignes pH/redox/chlore réglables, bornes min/max dynamiques par installation, sensors de volume/débit/temps de fonctionnement, télémétrie pompe à vitesse variable, capteur d'alerte active (`binary_sensor`, classe `problem`).
- **Toutes les données de l'API** : depuis la v1.7.0-perso, chaque champ restant renvoyé par l'API Klereo (~300 champs bruts) est exposé en `sensor` de diagnostic, désactivé par défaut. Rien n'est perdu, même les champs dont on ne connaît pas encore la signification exacte.

Voir `CHANGELOG.md` pour le détail complet.

## Décodage des plannings Klereo

La v1.8.0-perso décode automatiquement les 13 entrées `details["plans"]` renvoyées par Klereo. Les plans de 12 octets sont interprétés comme 96 créneaux de 15 minutes, avec les bits lus LSB-first.

- **Index 255** : planning de filtration. `0` = vitesse **V1**, `1` = vitesse **V2**.
- **Index 18** : planning d'écrémage. `0` = **OFF**, `1` = **ON**.
- **Index 254** : trois masques indépendants de 96 bits (`mask_0`, `mask_1`, `mask_2`), sans attribution de nom non vérifiée.
- Un sensor Home Assistant `Plan <index>` est créé pour chaque plan présent. Les index 255 et 18 sont nommés respectivement **Filtration Schedule** et **Skimming Schedule**.
- Chaque sensor expose les 96 créneaux dans `slots` et les plages compactées dans `schedule`, ainsi que `plan64`, `raw_hex` et `update_time`.

Pour le planning de filtration de l'installation de référence, le sensor 255 doit afficher : `V1 00:00-12:00 | V2 12:00-14:45 | V1 14:45-00:00`.

## Entités "diagnostic" désactivées par défaut

Une installation typique génère environ 55 entités curatées (activées) + ~300 entités brutes de diagnostic (désactivées). Pour activer une entité brute qui vous intéresse :

**Paramètres → Appareils et services → Klereo (perso) → cliquez sur l'appareil → onglet Entités → cochez "Afficher les entités désactivées"** → cliquez sur l'entité voulue → activez-la (roue crantée en haut à droite du dialogue) → redémarrez si demandé.

## Installation via HACS (dépôt personnalisé)

1. Dans Home Assistant : **HACS → Intégrations → menu ⋮ (en haut à droite) → Dépôts personnalisés**.
2. Renseignez :
   - **URL** : `https://github.com/<votre-compte>/<nom-de-ce-depot>`
   - **Catégorie** : `Intégration`
3. Cliquez **Ajouter**, puis cherchez **"Klereo (perso)"** dans HACS et installez-la.
4. Redémarrez Home Assistant.
5. **Paramètres → Appareils et services → Ajouter une intégration** → **Klereo (perso)** → entrez vos identifiants Klereo Connect.

Comme le domaine technique (`klereo_perso`) est différent de celui de l'intégration officielle (`klereo`), HACS les traite comme deux intégrations totalement indépendantes : aucune ne peut écraser l'autre, même en cas de mise à jour simultanée des deux.

## Mettre à jour ce fork plus tard

Poussez vos changements sur la branche par défaut de votre dépôt GitHub (ou créez un tag/une release si vous voulez versionner proprement) : HACS détectera la nouvelle version et proposera la mise à jour, exactement comme pour n'importe quelle intégration HACS.

## Tests

```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component ruff
pytest tests/ -v
```

## Crédits

- **Auteur original :** [JonBasse](https://github.com/JonBasse) — [ha-klereo](https://github.com/JonBasse/ha-klereo)
- **Plugin Jeedom original :** [MrWaloo/jeedom-klereo](https://github.com/MrWaloo/jeedom-klereo)

## Licence

MIT — voir `LICENSE`.

## Avertissement

Fork communautaire non officiel, non affilié à Klereo. Utilisation à vos risques.
