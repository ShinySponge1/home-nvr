ARG OLLAMA_BUILDER_IMAGE=golang:1.26.10-bookworm@sha256:23ce71337b726608afb1bc00986e630a05034a87a87ea1fc2cd1ae5cf33387eb
ARG OLLAMA_BASE_IMAGE=ollama/ollama:0.40.13@sha256:b2f0122c476bc9fe7ce679d8bb4bd555351e25e2554eefb156f61cb0a89cf429

FROM ${OLLAMA_BUILDER_IMAGE} AS ollama-build
WORKDIR /src
ADD --checksum=sha256:17c24d7268a286722d8e02d0f1d940a94922ecb73c20fb4377d2ebd7b1f9640c \
    https://codeload.github.com/ollama/ollama/tar.gz/04088e7c9d41cba5d33bafbf788d87a465c79d5b \
    /tmp/ollama.tar.gz
RUN tar -xzf /tmp/ollama.tar.gz --strip-components=1 && rm /tmp/ollama.tar.gz
COPY xnet-v0.62.0.patch /tmp/xnet-v0.62.0.patch
RUN git apply --check /tmp/xnet-v0.62.0.patch \
    && git apply /tmp/xnet-v0.62.0.patch \
    && test "$(go list -mod=readonly -m -f '{{.Version}}' golang.org/x/net)" = "v0.62.0" \
    && mkdir -p /out \
    && CGO_ENABLED=1 go build -mod=readonly -trimpath -buildmode=pie \
       -ldflags "-w -s -X=github.com/ollama/ollama/version.Version=0.40.13-security.1 -X=github.com/ollama/ollama/server.mode=release" \
       -o /out/ollama .

FROM ${OLLAMA_BASE_IMAGE}
LABEL org.opencontainers.image.title="Ollama security overlay" \
      org.opencontainers.image.version="0.40.13-security.1" \
      org.opencontainers.image.source="https://github.com/ShinySponge1/home-nvr" \
      org.opencontainers.image.revision="04088e7c9d41cba5d33bafbf788d87a465c79d5b"
COPY --from=ollama-build --chmod=0555 /out/ollama /bin/ollama
