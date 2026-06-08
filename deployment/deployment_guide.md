# TechInsights Production Deployment Guide

This guide covers running **TechInsights** locally under Docker Compose, managing migrations, and deploying the containerized stack onto modern cloud hosting platforms like **Render**, **Railway**, **DigitalOcean**, and **AWS/VPS**.

---

## Project Structure Overview

The project has been upgraded with the following deployment-ready assets:

```
Tech_Insights/
├── .github/workflows/
│   └── ci-cd.yml             # GitHub Actions CI pipeline
├── config/
│   ├── __init__.py           # Dynamic environment loader
│   └── settings.py           # Enterprise Config class (SQL Connection pools, Cookie security, etc.)
├── deployment/
│   └── deployment_guide.md   # This production guide
├── nginx/
│   └── nginx.conf            # Nginx proxy, Gzip compression, WebSocket upgrades, static caching
├── scripts/
│   └── entrypoint.sh         # Startup check (polls PG, runs flask db upgrade, starts Gunicorn)
├── .dockerignore             # Excludes large upload assets and secrets
├── .env.example              # Template containing all environment variable configurations
├── Dockerfile                # High performance multi-stage secure Python environment
├── docker-compose.yml        # Multi-container orchestration (Gunicorn, Postgres, Redis, Nginx)
├── extensions.py             # Refactored extensions adding Cache, Sessions, and Migrations
├── gunicorn.conf.py          # Production WSGI server utilizing async eventlet workers
└── app.py                    # Refactored main entrypoint loading dynamic configurations
```

---

## 1. Local Development under Docker Compose

To build and run the entire multi-container stack locally:

### Step 1: Prepare environment variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and adjust the variables (especially database passwords, Cloudinary keys, and SMTP credentials) if needed. The defaults are pre-configured to work out-of-the-box inside Docker Compose networks.

### Step 2: Build and run the containers
```bash
docker compose up --build -d
```
This command starts:
- **techinsights_db**: PostgreSQL 15 database.
- **techinsights_redis**: Redis 7 memory cache, session backend, and Socket.IO broker.
- **techinsights_web**: Gunicorn + Flask app (with auto-applied migrations).
- **techinsights_nginx**: Nginx reverse proxy serving static files and exposing ports 80/443.

### Step 3: Access the platform
Open your browser and navigate to `http://localhost`. The application is fully live and proxied through Nginx!

### Step 4: Shut down the stack
```bash
docker compose down -v
```
*(Note: `-v` will also delete the volume caches. Omit `-v` if you want your local database data to persist between runs).*

---

## 2. Managing Database Migrations

With **Flask-Migrate** and **Alembic** now integrated, you no longer rely on brittle raw SQL migration scripts:

- **Create a new migration** (whenever you update columns in `models.py`):
  ```bash
  docker compose exec web flask db migrate -m "Describe your schema changes"
  ```
- **Apply migrations in production**:
  The `scripts/entrypoint.sh` automatically executes `flask db upgrade` on container startup, ensuring your production schema matches your models instantly without manual intervention.

---

## 3. Production Cloud Deployment Strategies

### 🌐 Platform A: Render (Zero-Downtime SaaS Hosting)
Render allows running containerized services with instant build integrations:

1. **Deploying the Database**:
   - Create a new **PostgreSQL** instance on Render.
   - Copy the generated `External Database URL`.

2. **Deploying the Web Container**:
   - Create a new **Web Service** on Render, pointing to your GitHub repository.
   - Set the **Environment** option to `Docker`.
   - Under **Advanced Settings**, add the following environment variables:
     - `FLASK_ENV` = `production`
     - `DATABASE_URL` = *(Your Render PostgreSQL Connection URL)*
     - `SECRET_KEY` = *(Generate a secure random key)*
     - `JWT_SECRET_KEY` = *(Generate a secure random key)*
     - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
     - `EMAIL_USER`, `EMAIL_PASS`
     - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   - Set **Docker Build Context** = `.` and **Dockerfile Path** = `Dockerfile`.
   - Click **Deploy Web Service**. Render builds the multi-stage image, boots PostgreSQL, applies migrations, and brings the Flask app live automatically!

*(Optional: Render provides native SSL out-of-the-box, meaning you don't need a separate Nginx container on Render since their global load balancers handle reverse proxying, TLS termination, and static asset offloading automatically).*

---

### 🚀 Platform B: Railway (One-Click Docker Orchestration)
Railway is ideal for running multi-container stacks defined by `docker-compose.yml`:

1. Sign in to Railway and click **New Project** -> **Provision PostgreSQL**.
2. Click **New Project** -> **Provision Redis**.
3. Link your GitHub repository or use CLI `railway up`.
4. Railway reads the `Dockerfile` at the root and deploys your Flask app. Under **Variables**, link `DATABASE_URL` and `REDIS_URL` using Railway's reference templates:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL` = `${{Redis.REDIS_URL}}`
5. Railway terminates SSL and exposes a public domain for your web runner.

---

### ☁️ Platform C: DigitalOcean VPS / AWS EC2 (Dedicated Hosting)
For dedicated Virtual Private Servers (VPS):

1. **Install Docker & Docker Compose**:
   ```bash
   sudo apt-get update
   sudo apt-get install docker.io docker-compose-plugin -y
   ```
2. **Clone and Configure**:
   Clone your repository, copy `.env.example` to `.env` and fill in real production credentials.
3. **Run the stack**:
   ```bash
   docker compose up -d --build
   ```
4. **Setup SSL (Let's Encrypt / Certbot)**:
   Install certbot on the host:
   ```bash
   sudo apt-get install certbot -y
   sudo certbot certonly --standalone -d yourdomain.com
   ```
   Map the generated certificates in your `docker-compose.yml` under the `nginx` service:
   ```yaml
   volumes:
     - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
     - uploads_volume:/app/static/uploads:ro
     - /etc/letsencrypt:/etc/letsencrypt:ro # map certificates
   ```
   Uncomment the SSL server block in `nginx/nginx.conf`, replacing `yourdomain.com` with your real domain. Reload Nginx:
   ```bash
   docker compose exec nginx nginx -s reload
   ```

---

## 4. Production Security Hardening Checklist

- [ ] **Turn Debug Off:** Never run with `DEBUG=True` in production. Our `ProductionConfig` automatically enforces `DEBUG = False`.
- [ ] **Secure Cookies:** In production, session cookies are configured with `SESSION_COOKIE_SECURE = True` and `SESSION_COOKIE_HTTPONLY = True` to prevent XSS-based hijacking. *(Requires HTTPS to be active).*
- [ ] **Input Sanitization:** Keep using the implemented `sanitize_html` Quill handler backed by `bleach` to block malicious script injections.
- [ ] **Secrets Obfuscation:** Ensure `.env` is **NEVER** checked into source control (VCS). `.gitignore` has been updated to fully exclude it.
