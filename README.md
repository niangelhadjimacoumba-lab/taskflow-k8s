# TaskFlow — Migration d'une architecture monolithique vers des microservices sur Kubernetes

Projet de démonstration : une API de gestion de tâches, d'abord conçue comme une seule application,
puis **découpée en 3 microservices indépendants**, conteneurisés, orchestrés par Kubernetes,
avec un pipeline CI/CD complet et une stack d'observabilité (Prometheus/Grafana).

## Pourquoi ce projet

Ce dépôt illustre une démarche de migration réaliste :
1. Identifier les domaines métier (authentification, tâches, notifications)
2. Les isoler en services indépendants, chacun avec sa propre base de données
3. Les faire communiquer de façon découplée (Redis pub/sub plutôt que des appels synchrones en cascade)
4. Les déployer, superviser et faire évoluer indépendamment sur Kubernetes

## Architecture

```
                        ┌─────────────────┐
                        │   Ingress (nginx) │
                        └────────┬─────────┘
             ┌────────────────────┼────────────────────┐
             │                    │                     │
      /api/auth/*           /api/tasks/*         /api/notifications/*
             │                    │                     │
             ▼                    ▼                     ▼
     ┌───────────────┐   ┌────────────────┐   ┌───────────────────────┐
     │ auth-service   │   │ tasks-service  │   │ notifications-service │
     │ (FastAPI)      │   │ (FastAPI)      │   │ (FastAPI)              │
     │ SQLite users   │   │ SQLite tasks   │   │ stockage en mémoire    │
     └───────┬────────┘   └───────┬────────┘   └───────────┬────────────┘
             │ JWT                │ publish event          │ subscribe
             │                    ▼                         │
             │            ┌───────────────┐                 │
             └───────────▶│     Redis     │◀────────────────┘
               verifie JWT │  (pub/sub)    │
                           └───────────────┘

     Prometheus scrape /metrics sur les 3 services → Grafana (dashboards)
```

- **auth-service** : inscription, connexion, émission de JWT
- **tasks-service** : CRUD des tâches ; vérifie le JWT (secret partagé) ; publie un événement Redis
  à chaque création/complétion/suppression de tâche
- **notifications-service** : s'abonne au canal Redis, transforme les événements en notifications
  consultables par utilisateur

Chaque service expose `/health` (liveness/readiness) et `/metrics` (format Prometheus, via
`prometheus-fastapi-instrumentator`).

## Stack technique

| Domaine | Outils |
|---|---|
| API | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Messagerie inter-services | Redis (pub/sub) |
| Conteneurisation | Docker (build multi-stage) |
| Orchestration | Kubernetes (Deployments, Services, Ingress, ConfigMaps, Secrets) |
| CI/CD | GitHub Actions (tests, build, scan Trivy, push GHCR, validation manifests) |
| Observabilité | Prometheus, Grafana |
| Tests | Pytest, httpx |

## Lancer le projet en local (sans Kubernetes)

```bash
cp .env.example .env
docker compose up --build
```

- auth-service : http://localhost:8001/docs
- tasks-service : http://localhost:8002/docs
- notifications-service : http://localhost:8003/docs

Exemple de scénario complet :

```bash
# 1. Créer un compte
curl -X POST http://localhost:8001/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "secret123"}'

# 2. Se connecter -> récupérer le token
TOKEN=$(curl -s -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "secret123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 3. Créer une tâche
curl -X POST http://localhost:8002/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Préparer la demo"}'

# 4. Vérifier l'identité via JWT
curl http://localhost:8001/me -H "Authorization: Bearer $TOKEN"

# 5. Voir la notification générée automatiquement (user_id=1 si premier utilisateur)
curl http://localhost:8003/notifications/1
```

## Déployer sur Kubernetes (Minikube)

```bash
minikube start
minikube addons enable ingress

# Construire les images directement dans le registre Docker de Minikube
eval $(minikube docker-env)
docker build -t ghcr.io/niangelhadjimacoumba-lab/taskflow-auth-service:latest services/auth-service
docker build -t ghcr.io/niangelhadjimacoumba-lab/taskflow-tasks-service:latest services/tasks-service
docker build -t ghcr.io/niangelhadjimacoumba-lab/taskflow-notifications-service:latest services/notifications-service

# Déployer
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/tasks-service.yaml
kubectl apply -f k8s/notifications-service.yaml
kubectl apply -f k8s/ingress.yaml

# Monitoring
kubectl apply -f monitoring/

# Vérifier
kubectl get pods -n taskflow
minikube tunnel   # dans un autre terminal, pour exposer l'ingress
```

Ajouter ensuite `127.0.0.1 taskflow.local` dans `/etc/hosts`, puis tester :
`curl http://taskflow.local/api/auth/health`

## Accéder au monitoring

```bash
kubectl port-forward -n taskflow svc/grafana 3000:3000
kubectl port-forward -n taskflow svc/prometheus 9090:9090
```

Grafana (http://localhost:3000) est pré-configuré avec la datasource Prometheus et un dashboard
"TaskFlow - Vue d'ensemble" (requêtes/s, latence p95, taux d'erreurs 5xx par service).

## CI/CD

Le workflow `.github/workflows/ci-cd.yml` s'exécute à chaque push/PR :

1. **test** — exécute les tests Pytest de chaque service (matrice des 3 services)
2. **build-and-scan** — build l'image Docker de chaque service, scan de vulnérabilités avec
   Trivy, puis push vers GitHub Container Registry (uniquement sur `main`)
3. **validate-k8s-manifests** — valide la syntaxe et le schéma de tous les manifests Kubernetes
   avec `kubeconform`

## Tests

```bash
for svc in auth-service tasks-service notifications-service; do
  (cd services/$svc && pip install -r requirements.txt && python -m pytest tests/ -v)
done
```

Les tests sont indépendants (bases SQLite isolées, Redis mocké pour les tests unitaires).

## Pistes d'amélioration

- Remplacer SQLite par PostgreSQL (un par service) pour un vrai usage multi-pods
- Ajouter un Horizontal Pod Autoscaler sur `tasks-service`
- Centraliser les logs (stack EFK/Loki) en complément des métriques
- Passer la gestion des secrets à un outil dédié (Sealed Secrets, Vault)
