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

All jobs run off a shared Docker Image within GCP. In order to run files locally within the context of this docker image follow these steps:

1. Build the image `docker build -t monitor-jobs:local .`
2. Run the job within the image. The following command mounts the local file of the repo in the image so that you don't have to rebuild the image for code changes. You will have to rebuild the image if you update dependencies though:

```bash
docker run --rm \                                                                      
  --mount type=bind,source="$(pwd)/src",target=/app/src \ 
  monitor-jobs:local \
  -m {path to code}
```

Where `{path to code}` is a `.` separated path to teh job you wish to run, e.g. `src.jobs.email_alerts`.
