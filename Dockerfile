FROM python:3.11.4-slim-bookworm
ARG NASPILOT_VERSION
ENV LANG="C.UTF-8" \
    TZ="Asia/Shanghai" \
    HOME="/naspilot" \
    CONFIG_DIR="/config" \
    TERM="xterm" \
    PUID=0 \
    PGID=0 \
    UMASK=000 \
    PORT=3001 \
    NGINX_PORT=3000 \
    PROXY_HOST="" \
    NASPILOT_AUTO_UPDATE=release \
    AUTH_SITE="iyuu" \
    IYUU_SIGN=""
WORKDIR "/app"
RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get -y install \
        musl-dev \
        nginx \
        gettext-base \
        locales \
        procps \
        gosu \
        bash \
        wget \
        curl \
        busybox \
        dumb-init \
        jq \
        haproxy \
        fuse3 \
        rsync \
        ffmpeg \
        nano \
    && \
    if [ "$(uname -m)" = "x86_64" ]; \
        then ln -s /usr/lib/x86_64-linux-musl/libc.so /lib/libc.musl-x86_64.so.1; \
    elif [ "$(uname -m)" = "aarch64" ]; \
        then ln -s /usr/lib/aarch64-linux-musl/libc.so /lib/libc.musl-aarch64.so.1; \
    fi \
    && curl https://rclone.org/install.sh | bash \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf \
        /tmp/* \
        /naspilot/.cache \
        /var/lib/apt/lists/* \
        /var/tmp/*
COPY requirements.txt requirements.txt
RUN apt-get update -y \
    && apt-get install -y build-essential \
    && pip install --upgrade pip \
    && pip install Cython \
    && pip install -r requirements.txt \
    && playwright install-deps chromium \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf \
        /tmp/* \
        /naspilot/.cache \
        /var/lib/apt/lists/* \
        /var/tmp/*
COPY . .
RUN cp -f /app/nginx.conf /etc/nginx/nginx.template.conf \
RUN cp -f /app/update /usr/local/bin/mp_update \
RUN cp -f /app/entrypoint /entrypoint \
RUN chmod +x /entrypoint /usr/local/bin/mp_update \
RUN mkdir -p ${HOME} /var/lib/haproxy/server-state \
RUN groupadd -r naspilot -g 911 \
RUN useradd -r naspilot -g naspilot -d ${HOME} -s /bin/bash -u 911 \
RUN python_ver=$(python3 -V | awk '{print $2}') \
RUN echo "/app/" > /usr/local/lib/python${python_ver%.*}/site-packages/app.pth \
RUN echo 'fs.inotify.max_user_watches=5242880' >> /etc/sysctl.conf \
RUN echo 'fs.inotify.max_user_instances=5242880' >> /etc/sysctl.conf \
RUN locale-gen zh_CN.UTF-8 \
RUN FRONTEND_VERSION=$(curl -sL "https://api.github.com/repos/fortunearterial/NasPilot-Frontend/releases/latest" | jq -r .tag_name) \
    && curl -sL "https://github.com/fortunearterial/NasPilot-Frontend/releases/download/${FRONTEND_VERSION}/dist.zip" | busybox unzip -d / - \
    && mv /dist /public \
    && curl -sL "https://github.com/jxxghp/MoviePilot-Plugins/archive/refs/heads/main.zip" | busybox unzip -d /tmp - \
    && mv -f /tmp/MoviePilot-Plugins-main/plugins/* /app/app/plugins/ \
    && rm -rf /tmp/*
EXPOSE 3000
VOLUME [ "/config" ]
ENTRYPOINT [ "/entrypoint" ]
