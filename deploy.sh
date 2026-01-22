#!/bin/bash
# Alex Todo Dashboard - Deployment Script

echo "🚀 Déploiement du Todo Dashboard..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data

# Create systemd service file
sudo tee /etc/systemd/system/todo-dashboard.service > /dev/null <<EOF
[Unit]
Description=Alex Todo Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable todo-dashboard
sudo systemctl start todo-dashboard

echo "✅ Dashboard déployé!"
echo "📊 Accessible sur http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Commandes utiles:"
echo "  sudo systemctl status todo-dashboard  # Voir le statut"
echo "  sudo systemctl restart todo-dashboard # Redémarrer"
echo "  sudo journalctl -u todo-dashboard -f  # Voir les logs"
