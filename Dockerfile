FROM python:3.13-slim

ENV UTHERE_DB=/var/lib/uthere/uthere.db
ENV UTHERE_SOCKET=/tmp/uthere.sock

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/lib/uthere

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

VOLUME ["/var/lib/uthere"]

CMD ["uthere", "serve"]
