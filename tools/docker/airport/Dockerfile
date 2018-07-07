FROM ubuntu

LABEL Description "Airport wsgi and game server"

MAINTAINER Albert Hopkins <marduk@python.net>

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    mercurial \
    python3 \
    python3-dev \
    python3-pip \
    && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -c "Airport Server" -U -d /opt/airport -m airport

USER airport

RUN hg clone https://bitbucket.org/marduk/airport /opt/airport/airport && \
    pip3 -q install -U --user setuptools wheel && \
    pip3 -q install -U --user gunicorn psycopg2 -r/opt/airport/airport/requirements.txt


COPY settings.py urls.py /opt/airport/airport/djangoproject/djangoproject/

COPY entrypoint.sh /opt/airport

CMD ["/opt/airport/entrypoint.sh"]