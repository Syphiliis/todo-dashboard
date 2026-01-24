# Déploiement des Modifications sur le Serveur

## Changements Effectués

✅ **Backend (bot.py)**: Sauvegarde des guides IA dans la base de données
✅ **Frontend (index.html)**: Affichage des guides sur le dashboard
✅ **Script restart.sh**: Amélioration pour tuer toutes les instances avant redémarrage

## Instructions de Déploiement

### 1. Se connecter au serveur

```bash
ssh ubuntu@<ton-serveur-ip>
```

### 2. Aller dans le dossier du projet

```bash
cd /home/ubuntu/todo-dashboard
```

### 3. Pull les dernières modifications

```bash
git pull origin main
```

### 4. Redémarrer les services

```bash
./restart.sh
```

Le script amélioré va maintenant:
- ✅ Tuer TOUTES les instances de bot.py avec `pkill -9`
- ✅ Vérifier manuellement qu'il ne reste aucun processus
- ✅ Afficher un message de confirmation
- ✅ Redémarrer une seule instance propre

### 5. Vérifier que tout fonctionne

```bash
# Vérifier les logs
tail -f bot.log

# Vérifier qu'il n'y a qu'une seule instance
ps aux | grep "python.*bot.py" | grep -v grep
```

Tu devrais voir **une seule ligne** avec le nouveau PID.

## Test de la Fonctionnalité

### Via Telegram

1. Envoie une nouvelle tâche:
   ```
   /add passer du temps avec Emma
   ```

2. L'IA va générer un guide avec des étapes

3. Valide la tâche (réponds "ok" ou aux questions)

### Sur le Dashboard

1. Ouvre le dashboard web
2. La tâche devrait maintenant afficher:
   - Le titre
   - **Le guide complet avec les étapes** (nouveau!)
   - La catégorie et les métadonnées

## En Cas de Problème

Si le conflit persiste après `./restart.sh`:

```bash
# Méthode manuelle agressive
pkill -9 -f "python.*bot.py"
sleep 3
ps aux | grep bot.py  # Vérifier qu'il n'y a plus rien

# Redémarrer manuellement
cd /home/ubuntu/todo-dashboard
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &

# Noter le PID
echo $!
```

## Fichiers Modifiés

- `bot.py` - Logique de sauvegarde des guides
- `static/index.html` - Affichage des guides
- `restart.sh` - Amélioration du nettoyage des processus
- `fix_bot_conflict.sh` - Script de secours (si besoin)
