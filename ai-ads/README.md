# Pub IA : publicités Facebook / Instagram écrites par l'IA

Vous décrivez votre commerce et votre produit. L'IA (Claude) écrit plusieurs
publicités avec des angles différents. Vous choisissez la meilleure, ajoutez une
image et un lien, et l'outil la crée sur votre compte publicitaire Meta.

**Sécurité budget :** tout est créé **en pause**. Aucun euro n'est dépensé tant que
vous n'avez pas vérifié et activé la campagne vous-même dans le
Gestionnaire de publicités.

## 1. Installer

```bash
cd ai-ads
pip install -r requirements.txt
cp .env.example .env     # puis remplissez .env
python app.py            # ouvrez http://localhost:5000
```

## 2. La clé de l'IA

Créez une clé sur [console.anthropic.com](https://console.anthropic.com) (API Keys),
puis mettez-la dans `ANTHROPIC_API_KEY`. Chaque génération coûte quelques centimes.

Cette clé suffit pour **écrire** les pubs. La suite ne sert qu'à les **publier**.

## 3. Brancher Facebook / Instagram (une seule fois)

Il vous faut :

1. **Un compte Business Manager** : [business.facebook.com](https://business.facebook.com),
   avec votre **Page Facebook** et votre **compte publicitaire** (moyen de paiement ajouté).
2. **Une app Meta** : [developers.facebook.com](https://developers.facebook.com) →
   Créer une app → type « Entreprise » → ajoutez le produit **Marketing API**.
3. **Un jeton d'accès** : dans Business Manager → Paramètres → Utilisateurs système →
   créez un utilisateur système (Admin), donnez-lui accès à la Page et au compte publicitaire,
   puis « Générer un jeton » avec les autorisations `ads_management`, `ads_read`,
   `pages_read_engagement`, `pages_show_list` (et `instagram_basic` pour Instagram).
   Ce jeton va dans `META_ACCESS_TOKEN`.
4. **Les identifiants** :
   - `META_AD_ACCOUNT_ID` : le numéro du compte publicitaire (visible dans le Gestionnaire de publicités).
   - `META_PAGE_ID` : Page Facebook → À propos → Transparence de la Page → ID.
   - `META_INSTAGRAM_USER_ID` (facultatif) : l'ID du compte Instagram pro relié à la Page
     (Business Manager → Comptes → Comptes Instagram). Sans lui, la pub ne passe que sur Facebook.

Pour vos propres comptes, l'accès « standard » à l'API Marketing suffit en général.
Si Meta demande une vérification de l'entreprise ou un examen de l'app, il faut la faire
dans le tableau de bord développeur. Cela peut prendre quelques jours.

## Ce que l'outil crée

Pour chaque pub publiée : une campagne (objectif Trafic) → un ensemble de publicités
(budget par jour, pays, âge, Facebook + Instagram) → une création (texte, titre, image,
bouton) → la publicité. Les quatre sont en pause.

## Fichiers

- `app.py` : le site web (Flask)
- `ad_writer.py` : écriture des pubs par l'IA (réponse JSON structurée)
- `meta_ads.py` : création des pubs via l'API Marketing de Meta
- `templates/index.html` : la page

## Limites

- Ne gère pas encore les vidéos, les carrousels, ni le suivi des résultats (clics, coût).
- Pas de comptes utilisateurs : à lancer sur votre ordinateur ou un serveur privé, pas en public.
- Les pubs passent quand même par la vérification de Meta une fois activées.
