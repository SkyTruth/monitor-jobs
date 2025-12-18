# Monitor Jobs

Repo containing cron jobs that support monitor

## Getting Started

* Install dependencies with poetry

```bash
poetry install
```

* Install the pre-commit hooks

```bash
poetry run pre-commit install
```

## Structure

Each job defined in the `jobs` directory at `src/jobs` is deployed as a cloud run job triggered by a cloud scheduler. The scheduler is set in the github actions

```yaml
deploy-email-alerts-scheduler:
    needs: [build-and-push-docker, deploy-email-alerts]
    uses: ./.github/workflows/deploy-scheduler.yaml
    with:
      job_name: email-alerts
      scheduler_name: run-email-alerts
      schedule: "1 * * * *"  <== Schedule set here for each scheduler
```

## Adding a New Job

Add a new python file that can be executed via a CLI call of `python -m my-nifty-job.py`, to the `jobs` directory. Test your code thoroughly - See [Developing Locally](#developing-locally). Then add two new jobs to the `deploy.yaml` script within `.github/workspaces/deploy.yaml`. These jobs should look like this:

```yaml
deploy-{job-name}:
    needs: build-and-push-docker
    uses: ./.github/workflows/deploy-job.yaml
    with:
      job_name: "{job-name}"
      job_path: "{path to code}"

  
  deploy-email-alerts-scheduler:
    needs: [build-and-push-docker, {name of deploy job above}]
    uses: ./.github/workflows/deploy-scheduler.yaml
    with:
      job_name: {job-name}
      scheduler_name: run-{job-name}
      schedule: "1 * * * *"  # Whatever cron schedule you want to run on
```

Where `{job-name}` is a descriptive name of the job written in kabob case, and `{path to code}` is the path from the root of the repo to your script using `.` as a directory separator. For example: `src.jobs.email_alerts`

## Developing Locally

### Authentication

Many jobs integrate with GCP APIs in various ways, in cloud run these interactions are permitted via iam roles on the invoking service account. The safest way to be granted these authentications locally is to create your personal `Application Default Credentials (ADC)` and map them into the docker image. NOTE:  This requires your personal account to have the necessary permissions.

1. Create ADC with appropriate scopes for google drive

```bash
  gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/cloud-platform
```

2. Mount your local credentials, by adding the following to your `docker run` command - further explained in [Running Locally](#running-locally)

Linux/macOS

```bash
ADC_PATH="${HOME}/.config/gcloud/application_default_credentials.json"
docker run \
  -e GOOGLE_APPLICATION_CREDENTIALS="/tmp/keys/adc.json" \
  -v "${ADC_PATH}:/tmp/keys/adc.json:ro" \
  your-image-name

```

Windows

```bash
docker run ^
  -e GOOGLE_APPLICATION_CREDENTIALS="/tmp/keys/adc.json" ^
  -v "%AppData%/gcloud/application_default_credentials.json:/tmp/keys/adc.json:ro" ^
  your-image-name

```

### Running locally

All jobs run off a shared Docker Image within GCP. In order to run files locally within the context of this docker image follow these steps:

1. Build the image `docker build -t monitor-jobs:local .`
2. Run the job within the image. The following command mounts the local file of the repo in the image so that you don't have to rebuild the image for code changes. You will have to rebuild the image if you update dependencies though:

Linux/maxOS

```bash
docker run --rm \
  --mount type=bind,source="$(pwd)/src",target=/app/src \
  -e GOOGLE_APPLICATION_CREDENTIALS="/tmp/keys/adc.json" \
  -v "${ADC_PATH}:/tmp/keys/adc.json:ro" \
  monitor-jobs:local \
  -m {path to code}
```

Windows

```bash
docker run --rm \
  --mount type=bind,source="$(pwd)/src",target=/app/src \
  -e GOOGLE_APPLICATION_CREDENTIALS="/tmp/keys/adc.json" \
  -v "${ADC_PATH}:/tmp/keys/adc.json:ro" \
  monitor-jobs:local \
  -m {path to code}
```

Where `{path to code}` is a `.` separated path to teh job you wish to run, e.g. `src.jobs.email_alerts`.
