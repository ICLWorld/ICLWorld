ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}
WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG DEBIAN_MIRROR=deb.debian.org
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright VIC_DATA=/data VIC_ROOT=/app PYTHONDONTWRITEBYTECODE=1
COPY platform/requirements.lock.txt ./
RUN pip install --index-url ${PIP_INDEX_URL} --no-cache-dir -r requirements.lock.txt
ARG PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST
RUN sed -i "s|http://deb.debian.org|https://${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources && PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST=${PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST} python -m playwright install --with-deps --only-shell chromium
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libsdl2-dev libsdl2-ttf-dev xvfb x11vnc novnc websockify x11-utils fonts-noto-cjk ffmpeg && rm -rf /var/lib/apt/lists/*
COPY platform/ ./
RUN test -s scripts/os_alternate_desktop.js && test -s scripts/os_alternate_desktop.css
RUN pip install --index-url ${PIP_INDEX_URL} --no-cache-dir --no-deps '.[postgres]' && cmake -S apps/gomoku -B apps/gomoku/build && cmake --build apps/gomoku/build -j2
COPY os/ /opt/os-icl/
COPY release-lock.json /app/release-lock.json
RUN useradd --create-home --uid 10001 vic && mkdir -p /data /opt/os-icl/data && chown -R vic:vic /data /opt/os-icl/data && chmod -R a+rX /app /opt/ms-playwright
USER vic
CMD ["uvicorn","vic.main:create_app","--factory","--host","0.0.0.0","--port","8765","--workers","1"]
