FROM vllm/vllm-openai:v0.25.1-cu129@sha256:483a446d6b06a3757e4c7f5ca707e32443f49202bd382380dd969f90792e6a8d

ARG SOURCE_REPO="https://github.com/OWNER/agent-worm-poc"
ARG GIT_REVISION="unknown"
ARG BUILD_TIMESTAMP="unknown"
LABEL org.opencontainers.image.title="Agent Worm POC"
LABEL org.opencontainers.image.description="Prebuilt controlled POC runtime for open-weight LLM agent-worm research"
LABEL org.opencontainers.image.source="$SOURCE_REPO"
LABEL org.opencontainers.image.revision="$GIT_REVISION"
LABEL org.opencontainers.image.created="$BUILD_TIMESTAMP"
LABEL org.opencontainers.image.version="0.6.0"

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/workspace/hf-cache \
    AGENT_WORM_WORKSPACE=/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates coreutils curl git jq procps psmisc python3-venv tini unzip util-linux zip \
    && ln -sf "$(command -v python3)" /usr/local/bin/python \
    && python --version \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/jupyter-venv \
    && /opt/jupyter-venv/bin/python -m pip install --no-cache-dir --upgrade pip \
    && /opt/jupyter-venv/bin/python -m pip install --no-cache-dir \
         jupyterlab==4.4.6 \
         jupyter-server==2.18.2

WORKDIR /opt/agent-worm-poc
COPY . /opt/agent-worm-poc
RUN chmod +x /opt/agent-worm-poc/scripts/runpod/*.sh \
    && PYTHONPATH=/opt/agent-worm-poc/src python /opt/agent-worm-poc/scripts/release/release_audit.py \
    && cd /opt/agent-worm-poc && sha256sum -c SOURCE_HASHES.sha256 \
    && PYTHONPATH=/opt/agent-worm-poc/src python -m compileall -q /opt/agent-worm-poc/src /opt/agent-worm-poc/scripts /opt/agent-worm-poc/tests \
    && PYTHONPATH=/opt/agent-worm-poc/src python -m unittest discover -s /opt/agent-worm-poc/tests -v \
    && python -c "import vllm; assert vllm.__version__ == '0.25.1', vllm.__version__" \
    && printf '%s\n' \
       "{\"project\":\"agent-worm-poc\",\"version\":\"0.6.0\",\"vllm\":\"0.25.1\",\"base_image\":\"vllm/vllm-openai:v0.25.1-cu129@sha256:483a446d6b06a3757e4c7f5ca707e32443f49202bd382380dd969f90792e6a8d\",\"git_revision\":\"$GIT_REVISION\",\"build_timestamp\":\"$BUILD_TIMESTAMP\"}" \
       > /opt/agent-worm-runtime.json

ENV PYTHONPATH=/opt/agent-worm-poc/src
EXPOSE 8888
ENTRYPOINT ["/opt/agent-worm-poc/scripts/runpod/container_start.sh"]
