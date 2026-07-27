# Patient Intake Form

Veterinary patient intake form application for Animal Eye Iowa. Built with Streamlit.

## Features

- Web-based form for collecting veterinary patient intake data
- Integration with backend API for data submission
- Automated PDF generation of filled intake forms
- Email delivery of completed forms
- CAPTCHA protection against automated submissions

## Local Development

### Installation

1. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Configure secrets:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Edit secrets.toml with your credentials
   ```

### Running Locally

```bash
poetry run streamlit run patient_intake/app.py
```

### Development Commands

```bash
# Run tests
poetry run pytest

# Run linter
poetry run ruff check .

# Run type checker
poetry run mypy patient_intake/
```

## Docker

### Build and Run

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Build and run
docker compose up --build

# Or run in background
docker compose up -d --build
```

The app will be available at http://localhost:8501

### Build Image Only

```bash
docker build -t patient-intake-form .
```

## AWS Deployment

### Option 1: ECS Fargate (Recommended)

1. Push image to ECR:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
   docker tag patient-intake-form:latest <account>.dkr.ecr.us-east-1.amazonaws.com/patient-intake-form:latest
   docker push <account>.dkr.ecr.us-east-1.amazonaws.com/patient-intake-form:latest
   ```

2. Create ECS task definition with environment variables from AWS Secrets Manager

3. Deploy to Fargate with ALB

### Option 2: App Runner

1. Push to ECR (same as above)
2. Create App Runner service pointing to ECR image
3. Configure environment variables in App Runner console

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SERVICE_TOKEN` | API authentication token |
| `CATALOGUE_URL` | API endpoint for catalogues |
| `PATIENT_ADD_URL` | API endpoint for patient submission |
| `SMTP_SERVER` | SMTP server address |
| `SMTP_PORT` | SMTP port (usually 587) |
| `SMTP_LOGIN` | SMTP username (optional, defaults to `SENDER_EMAIL`) |
| `SENDER_EMAIL` | Email sender address (the `From` header) |
| `SENDER_PASSWORD` | SMTP password/app password |
| `RECIPIENT_EMAIL` | Email recipient address |
| `LOG_LEVEL` | Log verbosity (optional, defaults to `INFO`) |
| `SMTP_DEBUG` | Log the SMTP dialogue (optional, off by default) |

`SMTP_LOGIN` exists because not every provider authenticates with the sender
address. Amazon SES, for example, uses SMTP credentials whose username is a
credential id, while the `From` header must be a separately verified identity:

```
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_LOGIN=AKIAIOSFODNN7EXAMPLE
SENDER_PASSWORD=<SES SMTP password>
SENDER_EMAIL=verified-sender@your-domain.com
```

Leave `SMTP_LOGIN` unset for providers like Gmail, where the login is the
sender address.

The other email variables are all-or-nothing: if any of them is missing, the
whole email config is read from `secrets.toml` instead. `SMTP_LOGIN` is the
exception — it always overrides the login, whichever source is used. So a typo
in one of the other variables leaves you with an SES login against the server
from `secrets.toml`, which fails authentication: check that the whole group is
set, not just `SMTP_LOGIN`.

### Switching the deployment to Amazon SES

1. Add `SMTP_LOGIN` and the SES values to `/opt/<host>/.env` on the target host.
   The deploy workflow only pulls the image and runs `docker-compose up -d`
   against the compose file that already lives on the host, so changes to the
   `docker-compose.yml` in this repository do not reach the server on their own:
   make sure the host's compose file passes `SMTP_LOGIN` through (its `env_file:
   .env` already does, if present).
2. SES SMTP credentials are region-specific and the SMTP password is not an IAM
   secret access key — generate them for the same region as `SMTP_SERVER`.
3. While the SES account is in sandbox mode, `RECIPIENT_EMAIL` has to be a
   verified identity too, otherwise sending fails with `554 Message rejected`.

### Troubleshooting email delivery

The application logs to stdout, so the container output is the place to look:

```bash
docker compose logs -f patient-intake        # or: docker logs -f <container>
```

Every submission logs which config source was used, the SMTP server, the login
(masked) and whether the server accepted the message:

```
INFO patient_intake.config: Email config loaded from environment variables
INFO patient_intake.config: SMTP login taken from SMTP_LOGIN env var
INFO patient_intake.email_sender: Sending intake email for 'Fluffy' via email-smtp.us-east-1.amazonaws.com:587, login AKIA***, from sender@... to recipient@...
INFO patient_intake.email_sender: Intake email for 'Fluffy' accepted by email-smtp.us-east-1.amazonaws.com
```

`Email config loaded from secrets.toml` means the env vars were not fully set
and the values from `secrets.toml` were used instead — the log line lists which
variables were missing. Send failures are logged with a full traceback, while
the form only shows a generic message.

If the server accepts the message but it never arrives, set `SMTP_DEBUG=1` and
restart: the full SMTP dialogue, including the provider's response with the
message id, goes to the container's stderr. Turn it back off afterwards — that
trace also contains the AUTH exchange with the base64-encoded credentials.

## Project Structure

```
patient-intake-form/
├── pyproject.toml           # Poetry configuration
├── Dockerfile               # Docker build file
├── docker-compose.yml       # Docker Compose config
├── .env.example             # Environment template
├── patient_intake/          # Main package
│   ├── app.py               # Streamlit application
│   ├── config.py            # Configuration (env vars + secrets)
│   ├── api_client.py        # Backend API integration
│   ├── captcha.py           # CAPTCHA functionality
│   ├── email_sender.py      # Email sending
│   └── pdf_generator.py     # PDF generation
├── templates/               # PDF templates
└── tests/                   # Test directory
```
