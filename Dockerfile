
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
        openjdk-21-jre-headless \
        wget \
        unzip \
        libgoogle-perftools-dev \
        libsparsehash-dev \
        git \
        cmake \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://okapiframework.org/binaries/main/1.47.0/okapi-apps_gtk2-linux-x86_64_1.47.0.zip && \
    unzip -o okapi-apps_gtk2-linux-x86_64_1.47.0.zip \
        -d okapi-apps_gtk2-linux-x86_64_1.47.0 && \
    rm okapi-apps_gtk2-linux-x86_64_1.47.0.zip

COPY src ./src
COPY app.py .
COPY requirements.txt .

ENV DOCKER_ENV=1

RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download xx_ent_wiki_sm

CMD ["python", "app.py"]
