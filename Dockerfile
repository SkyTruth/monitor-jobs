# ─── Stage 1: builder ───
FROM python:3.12-slim-bookworm AS builder

ENV \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_HOME="/opt/poetry" \
  PATH="/opt/poetry/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      gdal-bin \
      libgdal-dev \
      libproj-dev \
      proj-data \
      proj-bin \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src/ ./

FROM python:3.12-slim-bookworm AS runtime

ENV \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_HOME="/opt/poetry" \
  PATH="/opt/poetry/bin:${PATH}"

# Install only runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      gdal-bin \
      libgdal32  \
      libproj25 \
      wget \
      curl \
      gnupg \
      ca-certificates \
      bzip2 \
      unzip \
      firefox-esr \
      xvfb \
    && rm -rf /var/lib/apt/lists/*

# geckodriver
ARG GECKODRIVER_VERSION=0.33.0
RUN wget -qO- https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz \
    | tar xvz -C /usr/local/bin

WORKDIR /app

# Python 3.12
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src

ENTRYPOINT ["python"]
CMD ["-c", "print('Specify a module to run')"]