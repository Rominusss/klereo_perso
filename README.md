# Klereo (perso) — fork patché pour Home Assistant

Fork personnel de [ha-klereo](https://github.com/JonBasse/ha-klereo) par JonBasse, avec des corrections et ajouts basés sur des diagnostics réels d'installation (voir `CHANGELOG` ci-dessous). Installé sous le domaine `klereo_perso`, il peut cohabiter sans conflit avec l'intégration officielle `klereo` installée via HACS.

## Pourquoi ce fork ?

- **Correctif** : sur le firmware actuel, les consignes réglables (température, pH, redox, chlore) sont exposées par l'API Klereo sous `details["params"]`, pas sous `details["RegulModes"]` comme le suppose l'intégration d'origine. Résultat : la consigne d'eau (`ConsigneEau`) n'était jamais créée en entité `number`. Ce fork lit les deux emplacements.
- **Nouvelles entités** : consignes pH/redox/chlore réglables, bornes min/max dynamiques par installation, sensors de volume/débit/temps de fonctionnement, télémétrie pompe à vitesse variable, capteur d'alerte active (`binary_sensor`, classe `problem`).

Voir `CHANGELOG.md` pour le détail complet.

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
