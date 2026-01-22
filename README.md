# 📋 Alex Todo Dashboard

Dashboard personnel de gestion de tâches avec notifications Telegram.

## 🚀 Installation rapide

```bash
# 1. Copier le dossier sur ton serveur
scp -r todo-dashboard/ user@ton-serveur:/home/user/

# 2. Se connecter au serveur
ssh user@ton-serveur

# 3. Aller dans le dossier
cd todo-dashboard

# 4. Lancer le déploiement
chmod +x deploy.sh
./deploy.sh
```

## 📁 Structure

```
todo-dashboard/
├── app.py              # Backend Flask + API
├── requirements.txt    # Dépendances Python
├── .env                # Configuration (Telegram, etc.)
├── deploy.sh           # Script de déploiement
├── data/
│   └── todos.db        # Base SQLite (créée auto)
└── static/
    └── index.html      # Frontend dashboard
```

## 🔧 Configuration

Édite le fichier `.env` :

```env
TELEGRAM_BOT_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id
PORT=5000
```

## 📡 API Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/todos` | Liste toutes les tâches |
| POST | `/api/todos` | Créer une tâche |
| PUT | `/api/todos/:id` | Modifier une tâche |
| DELETE | `/api/todos/:id` | Supprimer une tâche |
| GET | `/api/stats` | Statistiques |
| POST | `/api/daily-summary` | Envoyer résumé Telegram |
| POST | `/api/notify` | Notification custom |

### Exemples d'appels API

```bash
# Créer une tâche
curl -X POST http://localhost:5000/api/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Ma tâche", "category": "easynode", "priority": "urgent"}'

# Marquer comme terminée
curl -X PUT http://localhost:5000/api/todos/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

## 🔔 Notifications Telegram

Le dashboard envoie automatiquement des notifications :
- ✅ Quand une tâche est créée
- ✅ Quand une tâche est terminée
- ⏰ 1h avant chaque deadline
- 📊 Résumé quotidien (sur demande)

## 🛡️ Sécurité (optionnel)

Pour ajouter une authentification basique avec Nginx :

```nginx
location / {
    auth_basic "Todo Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:5000;
}
```

## 🔄 Intégration avec Claude

Claude peut interagir avec ton dashboard via l'API :

```python
# Claude peut créer des tâches
requests.post("http://ton-serveur:5000/api/todos", json={
    "title": "Nouvelle tâche depuis Claude",
    "category": "easynode",
    "priority": "important"
})
```

---
Créé avec ❤️ pour Alexandre | EasyNode
