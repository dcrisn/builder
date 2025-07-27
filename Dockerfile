FROM ubuntu:24.04 as base

# Docker environment variables
ENV DEBIAN_FRONTEND noninteractive

# install base system packages for build sdk etc.
RUN apt-get -y update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends \
    sudo \
    locales \
    wget \
    curl \
    vim \
    git \
    tree \
    strace \
    expect \
    socat \
    sshpass \
    lua5.1 \
    python3 \
    python3-pip \
    python3-mako \
    python3-yaml \
    build-essential \
    cmake \
    gawk \
    rename \
    gpg gpg-agent ca-certificates \
    unzip \
    libncurses5-dev libncursesw5-dev \
    cpio \
    rsync \
    bc \
    quilt \
	libssh2-1-dev \
	libssh2-1 \
	libidn2-0 \
	openssh-client \
	ncurses-base \ 
	libncurses5-dev \
	libncursesw5-dev \
	file \
    libpam-cap \
	libpam0g-dev \
	libsnmp-dev \
	libcap-dev \
	libcap2 \
	liblzma-dev \
    lua-socket \
    lua-socket-dev \
	libidn2-dev \
	libgnutls28-dev \
    libxml2 \
	libxml2-dev \
	gpg gpg-agent ca-certificates \
	gcc g++ \ 
	mkisofs \
	qemu-utils \
    libelf-dev \
    libgnutls30 \
    liblzma-dev \
    libnet-snmp-perl \
    libjansson-dev \
    iputils-ping \
    iproute2 \
    chrpath \
    lz4 \
    zstd

RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

# Install front-end required packages: nodejs, npm, html-minifier etc.
ARG NODEJS_VERSION_MAJOR=22
RUN curl -fsSL "https://deb.nodesource.com/setup_${NODEJS_VERSION_MAJOR}.x" | bash - && \
    apt-get install -y nodejs && \
    npm install --global typescript yarn

# Install html-minifier (needed for dumaos-build for frontend minification)
RUN npm --version
RUN npm install html-minifier -g

RUN echo 'debconf debconf/frontend select Noninteractive' | sudo debconf-set-selections && \
    ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime

# 1. Create new unprivileged user "dev" (added to sudoers below)
ARG USER
ARG GROUP
ARG UID
ARG GID

# ubuntu24 has default user 'ubuntu' with uid and gid 1000.
# if UID and GID are specified and conflict with this,
# we do *not* add them.
RUN if getent group ${GID} > /dev/null; then \
      echo "GID $GID already taken by group $(id -gn $GID), skipping groupadd."; \
    else \
      groupadd -g $GID $GROUP; \
    fi

RUN if getent passwd ${UID} > /dev/null; then \
      echo "UID $UID already taken by user $(id -un $UID), skipping user creation."; \
      usermod -s /bin/bash -aG $GID $(id -un $UID); \
      mkdir -p /home/$(id -un $UID)/dockerbuild/; \
      ln -sf /home/$(id -un $UID)/dockerbuild /home/$USER; \
      chown $UID:$UID /home/$USER; \
    else \
      useradd -m -l -s /bin/bash -u$UID -g$GID $USER; \
    fi

# don't require password when running command through sudo
RUN echo "$(id -un $UID) ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/10-$USER

USER $UID:$GID

# Copy ssh keys for ssh access to any internal servers
RUN mkdir -p /home/$USER/.ssh
ADD  --chown=$UID:$UID staging/files/system_config/ssh /home/$USER/.ssh/
COPY --chown=$UID:$UID staging/files/system_config/gitconfig /home/$USER/.gitconfig
ADD  --chown=$UID:$UID staging /home/$USER/base

ENV PATH="$PATH:/home/$USER/.local/bin"
ENV BASE_DIR "/home/$USER/base/"
ENV PYVENV "/home/$USER/pyvenv"
WORKDIR $BASE_DIR

# We are already in a sandbox: the container. A venv is redundant.
RUN pip3 install --break-system-packages -r depends/requirements.txt

# Environment variables and docker build args
ARG TARGET
ARG SDK_DIRNAME
ARG NUM_BUILD_CORES_CLI_FLAG
ARG BUILD_ARTIFACTS_OUTDIR
ARG DEV_BUILD_CLI_FLAG
ARG SHORT_CIRCUIT_MAGIC_CLI_FLAG

ENV INSIDE_CONTAINER "Y"
ENV SDK_TOPDIR "/home/$USER/$SDK_DIRNAME"
ENV BUILD_ARTIFACTS_OUTDIR "$BUILD_ARTIFACTS_OUTDIR"

RUN mkdir -p $BUILD_ARTIFACTS_OUTDIR

RUN /bin/bash -c "./builder.py -t $TARGET $DEV_BUILD_CLI_FLAG $NUM_BUILD_CORES_CLI_FLAG $SHORT_CIRCUIT_MAGIC_CLI_FLAG"

WORKDIR $SDK_TOPDIR
