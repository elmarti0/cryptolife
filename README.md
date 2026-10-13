# CryptoLife

Prototype open source de bot crypto autonome **en simulation uniquement**.
Python 3.10 ou plus; aucune dépendance à installer.

## Ce qui existe

- Portefeuille fictif BTC/USD persistant avec journal de décisions.
- Lecture de prix publics Coinbase; aucune clé API ni connexion à un compte.
- Stratégie explicite de moyennes mobiles 7/30 échantillons. Ce prototype
  n'est pas un modèle d'IA entraîné et ne garantit aucun bénéfice.
- Une position acheteuse au maximum, limitée à 25 % du capital lors de l'achat.
- Frais simulés de 0,6 % et glissement de 0,1 % par transaction. Ces valeurs
  sont des hypothèses de test, pas les tarifs d'une plateforme.
- Retraits fictifs limités aux bénéfices cumulés, après frais de liquidation.
- Sous 5 USD nets de liquidation : état DEAD irréversible dans ce portefeuille.
- Perte de 20 % depuis le sommet : liquidation simulée et état PAUSED.
- Persistance atomique, verrou contre deux processus et rejet des prix périmés.

## Essayer sans Internet

Dans le dossier du projet :

```bash
python3 bot.py --state data/demo.json init --capital 100
python3 bot.py --state data/demo.json demo --steps 180
python3 bot.py --state data/demo.json events
python3 -m unittest discover -s tests -v
```

La démo utilise des prix synthétiques reproductibles : ce n'est pas un backtest
et son résultat ne prédit pas le comportement sur les marchés.
Elle exige un portefeuille neuf et doit rester séparée du portefeuille public.

## Observer les prix réels avec de l'argent fictif

```bash
python3 bot.py init --capital 100
python3 bot.py run --interval 60
```

Laisse le processus tourner : les décisions commencent après 30 échantillons.
Ctrl+C arrête le processus et libère son verrou. Ensuite :

```bash
python3 bot.py status
python3 bot.py withdraw 10
python3 bot.py events
python3 bot.py pause
```

Un retrait exige un prix datant de moins de trois minutes : si nécessaire,
relance run puis arrête-le après une actualisation. Aucun argent n'est transféré.
Les montants sont exprimés en USD. Les retraits sont demandés par le propriétaire;
le bot ne se réapprovisionne jamais. La pause manuelle conserve la position et
son exposition; la pause de protection liquide la position fictive.
PAUSED et DEAD ne reprennent pas automatiquement. Un nouveau portefeuille
nécessite un nouveau chemin explicite; init refuse d'écraser un fichier existant.

En cas de crash brutal, le fichier .lock peut rester présent. Vérifie que le
processus est arrêté avant de supprimer ce verrou. Ne modifie pas manuellement
le JSON pendant une exécution. Ce stockage local ne constitue pas un audit inviolable.

## Limites et prochaines étapes

La simulation suppose une exécution immédiate, sans carnet d'ordres, exécution
partielle ou contraintes de lot. Les contrôles sont évalués au prochain prix
reçu; une panne réseau suspend les décisions, pas les mouvements du marché.
La fréquence d'échantillonnage peut varier pendant une panne. Une position peut
dépasser 25 % après un mouvement du prix. Pas de levier, de vente à découvert,
de paiements blockchain ni de retraits bancaires.

Le bot n'est pas un service hébergé : il tourne uniquement tant que le processus
sur ton ordinateur reste actif. Les huit tests automatiques, la démo en ligne
de commande et une récupération de prix public ont été vérifiés lors de la
création de cette version. Cela ne valide pas sa rentabilité ni son comportement
sur une longue période. Le mode réel reste à développer.

Étapes futures : backtests chronologiques sans fuite de données; comparaison
à une stratégie de référence; tableau de bord; modèle statistique évalué hors
échantillon; puis seulement étude d'un connecteur d'exécution réel avec limites
et gestion des incidents. Aucun résultat rentable n'est revendiqué.

API officielle : https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker

## Contribuer

Voir CONTRIBUTING.md. Le projet peut être publié sur GitHub, mais n'y est pas
encore publié. Cette version ne revendique aucune éligibilité à un programme
open source ni aucun contributeur externe.
